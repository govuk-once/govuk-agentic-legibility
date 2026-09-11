"""The durable workflow executor loop."""

import asyncio
from datetime import timedelta
import re
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Inform Temporal to allow imports that might otherwise be deemed unsafe in the sandbox
with workflow.unsafe.imports_passed_through():
    import pydantic

    import src.activities as activities
    from src.actions import apply_date_math
    from src.context import (
        AwaitingInput,
        InputSubmission,
        InterpreterState,
        StackFrame,
        TranscriptEntry,
    )
    from src.errors import DefinitionError, InputValidationError
    from src.model import (
        AssignState,
        CallState,
        ChoiceState,
        EndState,
        InputState,
        InvokeState,
        OutputState,
        SFSMDefinition,
        WaitState,
    )
    from src.paths import (
        interpolate,
        parse_duration,
        resolve_dict,
        resolve_path,
        set_path,
    )
    from src.predicates import evaluate
    from opentelemetry import trace as otel_trace

_tracer = otel_trace.get_tracer(__name__)


@workflow.defn
class SFSMInterpreter:
    def __init__(self) -> None:
        self.state = InterpreterState()
        self.definition: SFSMDefinition | None = None

        # State signals
        self._input_ready_event = asyncio.Event()
        self._awaiting_input: AwaitingInput | None = None
        self._received_input: Any | None = None
        self._timeout_triggered: bool = False

    @workflow.run
    async def run(
        self,
        definition_dict: dict[str, Any],
        initial_state: InterpreterState | None = None,
    ) -> Any:
        try:
            self.definition = SFSMDefinition.model_validate(definition_dict)
        except pydantic.ValidationError as e:
            workflow.logger.error(f"❌ Definition validation failed: {e}")
            raise DefinitionError(f"Invalid workflow definition: {e}") from e

        if initial_state:
            self.state = initial_state
            workflow.logger.info(
                f"Resuming workflow from initial_state context with frames: {self.state.frames}"
            )
        else:
            entry_process = self.definition.processes.get(self.definition.entry)
            if not entry_process:
                raise DefinitionError(
                    f"Entry process '{self.definition.entry}' not found in processes definition"
                )

            initial_vars = entry_process.vars.copy()
            self.state.frames.append(
                StackFrame(
                    process_id=self.definition.entry,
                    state_id=entry_process.start,
                    vars=initial_vars,
                )
            )
            workflow.logger.info(
                f"Started workflow entry process '{self.definition.entry}' at state '{entry_process.start}' "
                f"with initial vars: {initial_vars}"
            )

        max_transcript_length = 100
        min_steps_between_can = 0
        if self.definition.executor.continue_as_new:
            min_steps_between_can = self.definition.executor.continue_as_new.get(
                "min_steps_between", 50
            )

        steps_this_run = 0

        while self.state.frames:
            # Yield control back to Temporal event loop to prevent event starvation
            await asyncio.sleep(0)

            if (
                workflow.info().is_continue_as_new_suggested()
                and steps_this_run >= min_steps_between_can
            ):
                workflow.logger.info("Executing Continue-As-New...")
                workflow.continue_as_new(definition_dict, self.state)

            self.state.step_counter += 1
            steps_this_run += 1
            frame = self.state.frames[-1]
            process = self.definition.processes.get(frame.process_id)
            if not process:
                raise DefinitionError(f"Process '{frame.process_id}' not found")

            current_state = process.states.get(frame.state_id)

            if not current_state:
                workflow.logger.error(
                    f"❌ State '{frame.state_id}' not found in process '{frame.process_id}'"
                )
                raise DefinitionError(
                    f"State {frame.state_id} not found in {frame.process_id}"
                )

            workflow.logger.info(
                f"[Step {self.state.step_counter}] [{frame.process_id}:{frame.state_id}] ({type(current_state).__name__})"
            )

            # Prepare deterministic context for this step (MUST use workflow.now())
            context = {
                "input": frame.vars.get("input", {}),
                "env": self.state.env,
                "workflow_id": workflow.info().workflow_id,
                "step": self.state.step_counter,
                "__now__": workflow.now().isoformat(),
            }
            context.update(frame.vars)

            # --- INPUT STATE ---
            if isinstance(current_state, InputState):
                with _tracer.start_as_current_span(
                    "interpreter.InputState",
                    attributes={
                        "temporalWorkflowID": workflow.info().workflow_id,
                        "state_id": frame.state_id,
                        "process_id": frame.process_id,
                        "step": self.state.step_counter,
                        "prompt": current_state.prompt,
                        "schema_kind": current_state.schema_.kind,
                        "assign_target": current_state.assign,
                        "has_timeout": bool(current_state.timeout),
                        "has_options_from": bool(current_state.schema_.options_from),
                        "next_state": current_state.next,
                    },
                ) as input_span:
                    token = f"tkn_{self.state.step_counter}"
                    input_span.set_attribute("token", token)

                    options_from = getattr(current_state.schema_, "options_from", None)
                    static_options = getattr(current_state.schema_, "options", None)

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

                        
                    if current_state.timeout and "after" in current_state.timeout:
                        timeout_val = resolve_dict(current_state.timeout["after"], context)
                        if isinstance(timeout_val, str):
                            timeout_duration = parse_duration(timeout_val)
                            input_span.set_attribute("timeout_seconds", timeout_duration.total_seconds())
                        else:
                            raise DefinitionError(
                                "Timeout 'after' must resolve to a valid duration string"
                            )

                    prompt_text = interpolate(current_state.prompt, context)
                    input_span.set_attribute("prompt_resolved", prompt_text)

                    schema_dict = current_state.schema_.model_dump(
                        by_alias=True, exclude_none=True
                    )
                    if options is not None:
                        schema_dict["options"] = options

                    self._awaiting_input = AwaitingInput(
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
                    self._received_input = None
                    self._timeout_triggered = False
                    self._input_ready_event.clear()

                    workflow.logger.info(
                        f"Awaiting input token='{token}' prompt='{current_state.prompt}'"
                    )

                    if timeout_duration:
                        workflow.logger.info(f"⏱ Timeout set for {timeout_duration}")
                        try:
                            await workflow.wait_condition(
                                lambda: self._input_ready_event.is_set(),
                                timeout=timeout_duration,
                            )
                        except asyncio.TimeoutError:
                            self._timeout_triggered = True
                            workflow.logger.warn(
                                f"⚠️ Input timed out at state '{frame.state_id}'"
                            )
                    else:
                        await workflow.wait_condition(
                            lambda: self._input_ready_event.is_set()
                        )

                    self._awaiting_input = None

                    if self._timeout_triggered:
                        input_span.set_attribute("outcome", "timeout")
                        if current_state.timeout and "next" in current_state.timeout:
                            workflow.logger.info(
                                f"➡️ Timeout transition to '{current_state.timeout['next']}'"
                            )
                            frame.state_id = current_state.timeout["next"]
                            continue
                        raise DefinitionError(
                            f"Timeout triggered without 'next' route in state '{frame.state_id}'"
                        )
                    else:
                        input_span.set_attribute("outcome", "received")
                        input_span.set_attribute(
                            "received_value_type", type(self._received_input).__name__
                        )
                        input_span.set_attribute("received_value", str(self._received_input))
                        val = self._received_input

                    schema_kind = getattr(current_state.schema_, "kind", None)
                    if schema_kind in ["select_one", "select_many"]:
                        opts = options or static_options or []
                        val_key = getattr(current_state.schema_, "value_key", None)

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

                    normalise_rule = getattr(current_state.schema_, "normalise", None)
                    if isinstance(val, str) and normalise_rule:
                        if normalise_rule == "upper_trim":
                            val = val.strip().upper()
                        elif normalise_rule == "trim":
                            val = val.strip()
                        elif normalise_rule == "lower_trim":
                            val = val.strip().lower()

                    if isinstance(val, str) and val.strip() == "":
                        val = getattr(current_state.schema_, "default", None)

                    workflow.logger.info(
                            f"Input received for '{current_state.assign}': val={val} (type={type(val).__name__})"
                        )
                    set_path(frame.vars, current_state.assign, val)
                    frame.state_id = current_state.next

            # --- OUTPUT STATE ---
            elif isinstance(current_state, OutputState):
                with _tracer.start_as_current_span(
                    "interpreter.OutputState",
                    attributes={
                        "temporalWorkflowID": workflow.info().workflow_id,
                        "state_id": frame.state_id,
                        "process_id": frame.process_id,
                        "step": self.state.step_counter,
                        "channel": current_state.channel,
                        "has_template": bool(current_state.template),
                        "has_notification": current_state.channel != "transcript",
                        "on_error": current_state.on_error,
                        "next_state": current_state.next,
                    },
                ) as output_span:
                    if (
                        current_state.channel == "transcript"
                        or current_state.also_transcript
                    ):
                        msg = current_state.also_transcript or current_state.message or ""
                        msg = interpolate(msg, context)
                        output_span.set_attribute("message", msg[:500])
                        workflow.logger.info(f"Transcript output: '{msg}'")
                        self.state.transcript.append(
                            TranscriptEntry(
                                step=self.state.step_counter,
                                timestamp=workflow.now().isoformat(),
                                message=msg,
                            )
                        )
                        if len(self.state.transcript) > max_transcript_length:
                            self.state.transcript = self.state.transcript[
                                -max_transcript_length:
                            ]

                    if current_state.channel != "transcript":
                        notify_params = activities.NotifyParams(
                            channel=current_state.channel,
                            template=current_state.template or "",
                            params=resolve_dict(current_state.params or {}, context),
                        )
                        output_span.set_attribute("notification_template", current_state.template or "")
                        workflow.logger.info(
                            f"Sending notification via '{current_state.channel}'"
                        )
                        try:
                            await workflow.execute_activity(
                                activities.notify,
                                notify_params,
                                start_to_close_timeout=timedelta(seconds=30),
                                retry_policy=RetryPolicy(maximum_attempts=5),
                            )
                            output_span.set_attribute("notification_outcome", "success")
                        except Exception as e:
                            output_span.set_attribute("notification_outcome", "failed")
                            workflow.logger.error(f"Notification activity failed: {e}")
                            if current_state.on_error != "continue":
                                raise e

                    frame.state_id = current_state.next

            # --- CALL STATE ---
            elif isinstance(current_state, CallState):
                body = resolve_dict(current_state.body or {}, context)
                headers = current_state.headers or {}
                url = interpolate(current_state.url, context=context)
                service_name = getattr(current_state, "service", "")

                idempotency_key = None
                if getattr(current_state, "idempotency_key", None):
                    idempotency_key = interpolate(
                        current_state.idempotency_key, context
                    )

                with _tracer.start_as_current_span(
                    "interpreter.CallState",
                    attributes={
                        "temporalWorkflowID": workflow.info().workflow_id,
                        "state_id": frame.state_id,
                        "process_id": frame.process_id,
                        "step": self.state.step_counter,
                        "service": service_name,
                        "http.method": current_state.method,
                        "http.url": url,
                        "has_idempotency_key": bool(idempotency_key),
                        "assign_target": current_state.assign,
                        "capture_keys": ", ".join(current_state.capture.keys()),
                        "has_catch": bool(current_state.catch),
                        "next_state": current_state.next,
                    },
                ) as call_span:
                    call_params = activities.CallParams(
                        method=current_state.method,
                        url=url,
                        headers=headers,
                        body=body,
                        capture=current_state.capture or {},
                        service=service_name,
                        idempotency_key=idempotency_key,
                    )

                    workflow.logger.info(
                        f"🌐 HTTP {current_state.method} -> {service_name}:{url}"
                    )

                    self.state.transcript.append(
                        TranscriptEntry(
                            step=self.state.step_counter,
                            timestamp=workflow.now().isoformat(),
                            message=f"[ENGINE LOG] 🌐 Dispatched HTTP {current_state.method} request to service '{service_name}' ({url})",
                        )
                    )

                    retry_pol = RetryPolicy(
                        maximum_attempts=3,
                        non_retryable_error_types=["ValidationError"],
                    )

                    try:
                        result = await workflow.execute_activity(
                            activities.http_call,
                            call_params,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=retry_pol,
                        )
                        call_span.set_attribute("outcome", "success")
                        call_span.set_attribute(
                            "captured_keys", ", ".join(result.keys()) if isinstance(result, dict) else ""
                        )
                        set_path(frame.vars, current_state.assign, result)

                        self.state.transcript.append(
                            TranscriptEntry(
                                step=self.state.step_counter,
                                timestamp=workflow.now().isoformat(),
                                message=f"[ENGINE LOG] ✅ HTTP Call completed. Projected output assigned to '{current_state.assign}'",
                            )
                        )
                        frame.state_id = current_state.next
                    except Exception as e:
                        call_span.set_attribute("outcome", "error")
                        call_span.set_attribute("error_message", str(e)[:200])
                        workflow.logger.error(f"CallState activity error: {e}")
                        handled = False
                        if current_state.catch:
                            for c in current_state.catch:
                                if c["on"] == "any":
                                    call_span.set_attribute("error_handled_by", c["next"])
                                    frame.state_id = c["next"]
                                    handled = True
                                    break
                        if not handled:
                            raise e

            # --- CHOICE STATE ---
            elif isinstance(current_state, ChoiceState):
                matched = False
                for idx, rule in enumerate(current_state.rules):
                    eval_res = evaluate(rule.when, context)
                    workflow.logger.info(
                        f"Evaluating rule {idx}: when={rule.when} -> {eval_res}"
                    )
                    if eval_res:
                        workflow.logger.info(
                            f"Rule {idx} matched. Transitioning to '{rule.next}'"
                        )
                        frame.state_id = rule.next
                        matched = True
                        break
                if not matched:
                    workflow.logger.info(
                        f"No rules matched. Fallback to default '{current_state.default}'"
                    )
                    frame.state_id = current_state.default

            # --- ASSIGN STATE ---
            elif isinstance(current_state, AssignState):
                for k, v in current_state.set.items():
                    if isinstance(v, dict) and "op" in v:
                        op = v["op"]
                        if op == "add":
                            val1 = resolve_path(context, v.get("path", ""))
                            val2 = (
                                resolve_path(context, v.get("value_path", ""))
                                if "value_path" in v
                                else v.get("value")
                            )
                            if val1 is not None and val2 is not None:
                                set_path(frame.vars, k, val1 + val2)

                        elif op == "now_plus":
                            dur_path = v.get("value_path")
                            if dur_path:
                                dur_str = resolve_path(context, dur_path)
                                if dur_str:
                                    dt = workflow.now() + parse_duration(dur_str)
                                    set_path(frame.vars, k, dt.isoformat())

                        elif op in ["date_subtract", "date_add"]:
                            base_date = resolve_path(context, v.get("path", ""))
                            offset_str = v.get("value")
                            op_type = "add" if op == "date_add" else "subtract"
                            res_date = apply_date_math(
                                base_date, offset_str, op_type=op_type
                            )
                            set_path(frame.vars, k, res_date)

                        elif op in [
                            "date_before",
                            "before_now",
                            "is_true",
                            "is_false",
                            "eq",
                            "lt",
                            "gt",
                        ]:
                            res_bool = evaluate(v, context)
                            set_path(frame.vars, k, res_bool)

                    else:
                        set_path(frame.vars, k, resolve_dict(v, context))
                    workflow.logger.info(f"Assigned '{k}' = {frame.vars.get(k)}")
                frame.state_id = current_state.next

            # --- INVOKE STATE ---
            elif isinstance(current_state, InvokeState):
                target_proc = self.definition.processes.get(current_state.process)
                if not target_proc:
                    raise DefinitionError(
                        f"Process '{current_state.process}' invoked by state '{frame.state_id}' not found"
                    )

                frame.state_id = current_state.next

                new_frame = StackFrame(
                    process_id=current_state.process,
                    state_id=target_proc.start,
                    vars=target_proc.vars.copy(),
                    invoker_state=current_state,
                )

                resolved_inputs = {}
                if current_state.input:
                    resolved_inputs = resolve_dict(current_state.input, context)
                    new_frame.vars["input"] = resolved_inputs

                workflow.logger.info(
                    f"Invoking sub-process '{current_state.process}' "
                    f"with inputs: {resolved_inputs} | Frame variables initialized to: {new_frame.vars}"
                )

                self.state.transcript.append(
                    TranscriptEntry(
                        step=self.state.step_counter,
                        timestamp=workflow.now().isoformat(),
                        message=f"[ENGINE LOG] 🔀 Invoking sub-process stack frame '{current_state.process}' (Start state: '{target_proc.start}')",
                    )
                )

                self.state.frames.append(new_frame)

            # --- WAIT STATE ---
            elif isinstance(current_state, WaitState):
                dur_val = resolve_dict(current_state.duration, context)
                workflow.logger.info(f"💤 Sleeping for {dur_val}")
                if isinstance(dur_val, str):
                    await workflow.sleep(parse_duration(dur_val))
                else:
                    raise DefinitionError(
                        f"WaitState duration in '{frame.state_id}' must resolve to a valid string, got {type(dur_val).__name__}"
                    )
                frame.state_id = current_state.next

            # --- END STATE ---
            elif isinstance(current_state, EndState):
                workflow.logger.info(
                    f"🏁 Reached EndState '{frame.state_id}' in process '{frame.process_id}' "
                    f"(status={current_state.status}, outcome={current_state.outcome}) | Final vars: {frame.vars}"
                )

                ret_val = None
                if current_state.return_ is not None:
                    ret_val = resolve_dict(current_state.return_, context)

                popped_frame = self.state.frames.pop()
                if self.state.frames:
                    parent_frame = self.state.frames[-1]
                    invoker = popped_frame.invoker_state

                    if isinstance(invoker, InvokeState):
                        if invoker.assign and ret_val is not None:
                            set_path(parent_frame.vars, invoker.assign, ret_val)
                            workflow.logger.info(
                                f"↩️ Returned {ret_val} into parent var '{invoker.assign}'"
                            )

                        handled = False
                        if invoker.catch:
                            for c in invoker.catch:
                                rule_on = c.on if hasattr(c, "on") else c.get("on")
                                rule_next = (
                                    c.next if hasattr(c, "next") else c.get("next")
                                )
                                if rule_on == current_state.outcome or rule_on == "any":
                                    parent_frame.state_id = rule_next
                                    handled = True
                                    break
                else:
                    return {
                        "status": current_state.status,
                        "outcome": current_state.outcome,
                        "return": ret_val,
                    }

    @workflow.update
    async def submit_input(self, msg: InputSubmission) -> None:
        workflow.logger.info(f"📩 Input submitted via update: val={msg.value}")
        self._received_input = msg.value
        self._input_ready_event.set()

    @submit_input.validator
    def _validate_input(self, msg: InputSubmission) -> None:
        if not self._awaiting_input:
            workflow.logger.warn("❌ Rejected update: Workflow is not awaiting input")
            raise InputValidationError("Not awaiting input")
        if msg.token != self._awaiting_input.token:
            workflow.logger.warn(
                f"❌ Rejected update: Token mismatch ({msg.token} != {self._awaiting_input.token})"
            )
            raise InputValidationError(
                f"Token mismatch. Expected {self._awaiting_input.token}"
            )

        schema = self._awaiting_input.schema
        kind = (
            schema.get("kind")
            if isinstance(schema, dict)
            else getattr(schema, "kind", None)
        )
        val = msg.value

        if kind == "boolean" and not isinstance(val, bool):
            raise InputValidationError(
                f"Expected boolean, received {type(val).__name__}"
            )
        if kind == "string" and not isinstance(val, str):
            raise InputValidationError(
                f"Expected string, received {type(val).__name__}"
            )
        if kind == "string" and "pattern" in schema:
            if not re.match(str(schema["pattern"]), str(val)):
                raise InputValidationError(
                    schema.get("invalid_message", "Invalid format")
                )

        if kind in ["select_one", "select_many"]:
            options = (
                (
                    schema.get("options")
                    if isinstance(schema, dict)
                    else getattr(schema, "options", None)
                )
                or self._awaiting_input.options
                or []
            )

            # Explicit integer index check
            if kind == "select_one" and isinstance(val, int):
                idx = val - 1
                if 0 <= idx < len(options):
                    return

            v_key = (
                schema.get("value_key", "value")
                if isinstance(schema, dict)
                else getattr(schema, "value_key", "value")
            )
            valid_values = []
            for opt in options:
                if isinstance(opt, dict):
                    valid_values.append(
                        opt.get(v_key, opt.get("uprn", opt.get("id", opt.get("value"))))
                    )
                else:
                    valid_values.append(getattr(opt, "value", opt))

            if kind == "select_one":
                if val not in valid_values and val not in options:
                    raise InputValidationError(
                        f"Invalid selection: '{val}'. Please select a valid option."
                    )

            if kind == "select_many":
                if not isinstance(val, list):
                    raise InputValidationError(
                        "Expected list of values for select_many"
                    )
                for item in val:
                    if isinstance(item, int):
                        idx = item - 1
                        if 0 <= idx < len(options):
                            continue
                    if item not in valid_values and item not in options:
                        raise InputValidationError(
                            f"Invalid item '{item}' in selection list"
                        )

        if kind == "file_ref":
            if not isinstance(val, dict) or "error" in val:
                raise InputValidationError(
                    "Invalid file upload. Please use the upload button."
                )
            if not val.get("ref") or int(val.get("bytes", 0)) <= 0:
                raise InputValidationError(
                    "File payload missing valid reference or size."
                )

    @workflow.query
    def awaiting(self) -> AwaitingInput | None:
        return self._awaiting_input

    @workflow.query
    def transcript(self) -> list[TranscriptEntry]:
        return self.state.transcript

    @workflow.query
    def current_state_info(self) -> dict[str, Any] | None:
        if not self.state.frames:
            return None
        frame = self.state.frames[-1]
        process = (
            self.definition.processes.get(frame.process_id) if self.definition else None
        )
        state = process.states.get(frame.state_id) if process else None
        return {
            "process_id": frame.process_id,
            "state_id": frame.state_id,
            "state_type": type(state).__name__ if state else None,
            "step": self.state.step_counter,
        }
