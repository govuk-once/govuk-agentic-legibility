"""InputState handler — suspends execution and awaits structured input."""

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow

from src.actions import parse_duration
from src.context import AwaitingInput
from src.errors import DefinitionError
from src.paths import interpolate, resolve_dict, resolve_path, set_path


async def handle_input(state, frame, context, interpreter) -> dict[str, Any] | None:
    with interpreter.tracer.start_as_current_span(
        "interpreter.InputState",
        attributes={
            "temporalWorkflowID": workflow.info().workflow_id,
            "state_id": frame.state_id,
            "process_id": frame.process_id,
            "step": interpreter.state.step_counter,
            "prompt": state.prompt,
            "schema_kind": state.schema_.kind,
            "assign_target": state.assign,
            "has_timeout": bool(state.timeout),
            "has_options_from": bool(state.schema_.options_from),
            "next_state": state.next,
        },
    ) as input_span:
        token = f"tkn_{interpreter.state.step_counter}"
        input_span.set_attribute("token", token)

        options_from = getattr(state.schema_, "options_from", None)
        static_options = getattr(state.schema_, "options", None)

        options = None
        timeout_duration: timedelta | None = None
        prompt_text = ""
        if options_from:
            options = resolve_path(context, options_from)
        elif static_options:
            options = [
                opt.model_dump(by_alias=True, exclude_none=True)
                if hasattr(opt, "model_dump")
                else opt
                for opt in static_options
            ]

        if state.timeout and "after" in state.timeout:
            timeout_val = resolve_dict(state.timeout["after"], context)
            if isinstance(timeout_val, str):
                timeout_duration = parse_duration(timeout_val)
                input_span.set_attribute("timeout_seconds", timeout_duration.total_seconds())
            else:
                raise DefinitionError(
                    "Timeout 'after' must resolve to a valid duration string"
                )

        prompt_text = interpolate(state.prompt, context)
        input_span.set_attribute("prompt_resolved", prompt_text)

        schema_dict = state.schema_.model_dump(
            by_alias=True, exclude_none=True
        )
        if options is not None:
            schema_dict["options"] = options

        interpreter._awaiting_input = AwaitingInput(
            token=token,
            prompt=prompt_text,
            schema=schema_dict,
            options=options,
            timeout_seconds=timeout_duration.total_seconds()
            if timeout_duration
            else None,
            state_id=frame.state_id,
            state_type="InputState",
        )
        interpreter._received_input = None
        interpreter._timeout_triggered = False
        interpreter._input_ready_event.clear()

        workflow.logger.info(
            f"Awaiting input token='{token}' prompt='{state.prompt}'"
        )

        if timeout_duration:
            workflow.logger.info(f"⏱ Timeout set for {timeout_duration}")
            try:
                await workflow.wait_condition(
                    lambda: interpreter._input_ready_event.is_set(),
                    timeout=timeout_duration,
                )
            except asyncio.TimeoutError:
                interpreter._timeout_triggered = True
                workflow.logger.warn(
                    f"⚠️ Input timed out at state '{frame.state_id}'"
                )
        else:
            await workflow.wait_condition(
                lambda: interpreter._input_ready_event.is_set()
            )

        interpreter._awaiting_input = None

        if interpreter._timeout_triggered:
            input_span.set_attribute("outcome", "timeout")
            if state.timeout and "next" in state.timeout:
                workflow.logger.info(
                    f"➡️ Timeout transition to '{state.timeout['next']}'"
                )
                frame.state_id = state.timeout["next"]
                return None
            raise DefinitionError(
                f"Timeout triggered without 'next' route in state '{frame.state_id}'"
            )
        else:
            input_span.set_attribute("outcome", "received")
            input_span.set_attribute(
                "received_value_type", type(interpreter._received_input).__name__
            )
            input_span.set_attribute("received_value", str(interpreter._received_input))
            val = interpreter._received_input

        schema_kind = getattr(state.schema_, "kind", None)
        if schema_kind in ["select_one", "select_many"]:
            opts = options or static_options or []
            val_key = getattr(state.schema_, "value_key", None)

            if schema_kind == "select_one" and isinstance(val, int):
                idx = val - 1
                if 0 <= idx < len(opts):
                    opt_item = opts[idx]
                    if val_key in [
                        "uprn",
                        "single_line",
                        "address_line_1",
                    ] and isinstance(opt_item, dict):
                        val = opt_item
                    elif isinstance(opt_item, dict):
                        val = opt_item.get(
                            val_key or "value",
                            opt_item.get(
                                "uprn", opt_item.get("id", opt_item)
                            ),
                        )
                    else:
                        val = getattr(opt_item, "value", opt_item)

            elif schema_kind == "select_many" and isinstance(val, list):
                resolved_list = []
                for item in val:
                    if isinstance(item, int):
                        idx = item - 1
                        if 0 <= idx < len(opts):
                            opt_item = opts[idx]
                            if isinstance(opt_item, dict):
                                resolved_list.append(
                                    opt_item.get(
                                        val_key or "value",
                                        opt_item.get("id", opt_item),
                                    )
                                )
                            else:
                                resolved_list.append(
                                    getattr(opt_item, "value", opt_item)
                                )
                    else:
                        resolved_list.append(item)
                val = resolved_list

        normalise_rule = getattr(state.schema_, "normalise", None)
        if isinstance(val, str) and normalise_rule:
            if normalise_rule == "upper_trim":
                val = val.strip().upper()
            elif normalise_rule == "trim":
                val = val.strip()
            elif normalise_rule == "lower_trim":
                val = val.strip().lower()

        if isinstance(val, str) and val.strip() == "":
            val = getattr(state.schema_, "default", None)

        workflow.logger.info(
            f"Input received for '{state.assign}': val={val} (type={type(val).__name__})"
        )
        set_path(frame.vars, state.assign, val)
        frame.state_id = state.next
    return None
