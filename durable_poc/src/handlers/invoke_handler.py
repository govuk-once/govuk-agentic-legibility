"""InvokeState handler — pushes a sub-process stack frame."""

from typing import Any

from temporalio import workflow

from src.context import StackFrame, TranscriptEntry
from src.errors import DefinitionError
from src.paths import resolve_dict


async def handle_invoke(state, frame, context, interpreter) -> dict[str, Any] | None:
    target_proc = interpreter.definition.processes.get(state.process)
    if not target_proc:
        raise DefinitionError(
            f"Process '{state.process}' invoked by state '{frame.state_id}' not found"
        )

    frame.state_id = state.next

    new_frame = StackFrame(
        process_id=state.process,
        state_id=target_proc.start,
        vars=target_proc.vars.copy(),
        invoker_state=state,
    )

    resolved_inputs = {}
    if state.input:
        resolved_inputs = resolve_dict(state.input, context)
        new_frame.vars["input"] = resolved_inputs

    workflow.logger.info(
        f"Invoking sub-process '{state.process}' "
        f"with inputs: {resolved_inputs} | Frame variables initialized to: {new_frame.vars}"
    )

    interpreter.state.transcript.append(
        TranscriptEntry(
            step=interpreter.state.step_counter,
            timestamp=workflow.now().isoformat(),
            message=f"[ENGINE LOG] 🔀 Invoking sub-process stack frame '{state.process}' (Start state: '{target_proc.start}')",
        )
    )

    interpreter.state.frames.append(new_frame)
    return None
