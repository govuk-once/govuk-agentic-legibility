"""CallState handler — dispatches HTTP calls via Temporal activities."""

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

import src.activities as activities
from src.context import TranscriptEntry
from src.paths import interpolate, resolve_dict, set_path


async def handle_call(state, frame, context, interpreter) -> dict[str, Any] | None:
    """Dispatch an HTTP API call via a Temporal activity and capture the response.

    Resolves the request body, URL, headers, and optional idempotency key
    from *context*, then executes the ``http_call`` activity.  Successful
    responses are projected through ``state.capture`` and assigned into
    frame variables.  On failure the handler evaluates ``state.catch``
    rules; unmatched errors are re-raised.

    Two transcript entries are appended: one on dispatch and one on
    completion.  An OTEL span ``interpreter.CallState`` is emitted with
    service, HTTP method/URL, outcome, and error-handling attributes.

    Args:
        state: The ``CallState`` model for the current step.
        frame: The active ``StackFrame`` (mutated: ``state_id``, ``vars``).
        context: Deterministic step context dict.
        interpreter: The ``SFSMInterpreter`` instance providing the
            transcript list, step counter, and tracer.

    Returns:
        ``None`` to continue the interpreter loop.
    """
    body = resolve_dict(state.body or {}, context)
    headers = state.headers or {}
    url = interpolate(state.url, context=context)
    service_name = getattr(state, "service", "")

    idempotency_key = None
    if getattr(state, "idempotency_key", None):
        idempotency_key = interpolate(state.idempotency_key, context)

    with interpreter.tracer.start_as_current_span(
        "interpreter.CallState",
        attributes={
            "temporalWorkflowID": workflow.info().workflow_id,
            "state_id": frame.state_id,
            "process_id": frame.process_id,
            "step": interpreter.state.step_counter,
            "service": service_name,
            "http.method": state.method,
            "http.url": url,
            "has_idempotency_key": bool(idempotency_key),
            "assign_target": state.assign,
            "capture_keys": ", ".join(state.capture.keys()),
            "has_catch": bool(state.catch),
            "next_state": state.next,
        },
    ) as call_span:
        call_params = activities.CallParams(
            method=state.method,
            url=url,
            headers=headers,
            body=body,
            capture=state.capture or {},
            service=service_name,
            idempotency_key=idempotency_key,
        )

        workflow.logger.info(
            f"🌐 HTTP {state.method} -> {service_name}:{url}"
        )

        interpreter.state.transcript.append(
            TranscriptEntry(
                step=interpreter.state.step_counter,
                timestamp=workflow.now().isoformat(),
                message=f"[ENGINE LOG] 🌐 Dispatched HTTP {state.method} request to service '{service_name}' ({url})",
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
            set_path(frame.vars, state.assign, result)

            interpreter.state.transcript.append(
                TranscriptEntry(
                    step=interpreter.state.step_counter,
                    timestamp=workflow.now().isoformat(),
                    message=f"[ENGINE LOG] ✅ HTTP Call completed. Projected output assigned to '{state.assign}'",
                )
            )
            frame.state_id = state.next
        except Exception as e:
            call_span.set_attribute("outcome", "error")
            call_span.set_attribute("error_message", str(e)[:200])
            workflow.logger.error(f"CallState activity error: {e}")
            handled = False
            if state.catch:
                for c in state.catch:
                    if c["on"] == "any":
                        call_span.set_attribute("error_handled_by", c["next"])
                        frame.state_id = c["next"]
                        handled = True
                        break
            if not handled:
                raise e
    return None
