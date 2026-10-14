"""WaitState handler — durably sleeps for an ISO 8601 duration."""

from typing import Any

from temporalio import workflow

from src.actions import parse_duration
from src.errors import DefinitionError
from src.paths import resolve_dict


async def handle_wait(state, frame, context, interpreter) -> dict[str, Any] | None:
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
