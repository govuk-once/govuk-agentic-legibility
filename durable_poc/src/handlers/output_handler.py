"""OutputState handler — emits transcript entries and dispatches notifications."""

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

import src.activities as activities
from src.context import TranscriptEntry
from src.paths import interpolate, resolve_dict


async def handle_output(state, frame, context, interpreter) -> dict[str, Any] | None:
    with interpreter.tracer.start_as_current_span(
        "interpreter.OutputState",
        attributes={
            "temporalWorkflowID": workflow.info().workflow_id,
            "state_id": frame.state_id,
            "process_id": frame.process_id,
            "step": interpreter.state.step_counter,
            "channel": state.channel,
            "has_template": bool(state.template),
            "has_notification": state.channel != "transcript",
            "on_error": state.on_error,
            "next_state": state.next,
        },
    ) as output_span:
        if state.channel == "transcript" or state.also_transcript:
            msg = state.also_transcript or state.message or ""
            msg = interpolate(msg, context)
            output_span.set_attribute("message", msg[:500])
            workflow.logger.info(f"Transcript output: '{msg}'")
            interpreter.state.transcript.append(
                TranscriptEntry(
                    step=interpreter.state.step_counter,
                    timestamp=workflow.now().isoformat(),
                    message=msg,
                )
            )
            if len(interpreter.state.transcript) > interpreter.MAX_TRANSCRIPT_LENGTH:
                interpreter.state.transcript = interpreter.state.transcript[
                    -interpreter.MAX_TRANSCRIPT_LENGTH:
                ]

        if state.channel != "transcript":
            notify_params = activities.NotifyParams(
                channel=state.channel,
                template=state.template or "",
                params=resolve_dict(state.params or {}, context),
            )
            output_span.set_attribute("notification_template", state.template or "")
            workflow.logger.info(
                f"Sending notification via '{state.channel}'"
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
                if state.on_error != "continue":
                    raise e

        frame.state_id = state.next
    return None
