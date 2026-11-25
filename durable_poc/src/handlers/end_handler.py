"""EndState handler — pops the stack frame and returns control."""

from typing import Any

from temporalio import workflow

from src.model import InvokeState
from src.paths import resolve_dict, set_path


async def handle_end(state, frame, context, interpreter) -> dict[str, Any] | None:
    """Terminates the current process.
    
    Pops the current frame. If the current frame was invoked by another process, returns
    any required value to the invoker. Otherwise, returns a result disctionary to the interpreter.
    
    Args:
        state: The ``WaitState`` model for the current step.
        frame: The active ``StackFrame`` (mutated: ``state_id``, ``vars``).
        context: Deterministic step context dict.
        interpreter: The ``SFSMInterpreter`` instance (used for logging).

    Returns:
        dict containing status, outcome and a possibly null return value if there is no parent process 
        calling the current frame or ``None`` to continue the interpreter loop.

    """
    workflow.logger.info(
        f"🏁 Reached EndState '{frame.state_id}' in process '{frame.process_id}' "
        f"(status={state.status}, outcome={state.outcome}) | Final vars: {frame.vars}"
    )

    ret_val = None
    if state.return_ is not None:
        ret_val = resolve_dict(state.return_, context)

    popped_frame = interpreter.state.frames.pop()
    if interpreter.state.frames:
        parent_frame = interpreter.state.frames[-1]
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
                    if rule_on == state.outcome or rule_on == "any":
                        parent_frame.state_id = rule_next
                        handled = True #noqa F841
                        break
    else:
        return {
            "status": state.status,
            "outcome": state.outcome,
            "return": ret_val,
        }
    return None
