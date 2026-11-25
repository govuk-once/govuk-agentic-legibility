"""WaitState handler — durably sleeps for an ISO 8601 duration."""

from typing import Any

from temporalio import workflow

from src.actions import parse_duration
from src.errors import DefinitionError
from src.paths import resolve_dict


async def handle_wait(state, frame, context, interpreter) -> dict[str, Any] | None:
    """Pause the workflow for a set amount of time.

    The required time duration is expected as an ISO8601 string and is resolved from the context.
    
    Args:
        state: The ``WaitState`` model for the current step.
        frame: The active ``StackFrame`` (mutated: ``state_id``, ``vars``).
        context: Deterministic step context dict.
        interpreter: The ``SFSMInterpreter`` instance (used for logging).

    Returns:
        ``None`` to continue the interpreter loop.

    Raises:
        DefinitionError: If an operation raises ``ValueError`` (e.g.
                invalid ISO8601 duration).
    """
    dur_val = resolve_dict(state.duration, context)
    workflow.logger.info(f"💤 Sleeping for {dur_val}")
    if isinstance(dur_val, str):
        await workflow.sleep(parse_duration(dur_val))
    else:
        raise DefinitionError(
            f"WaitState duration in '{frame.state_id}' must resolve to a valid string, got {type(dur_val).__name__}"
        )
    frame.state_id = state.next
    return None
