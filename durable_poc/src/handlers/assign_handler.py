"""AssignState handler — executes operations via the registry."""

from typing import Any

from temporalio import workflow

from src.actions import REGISTRY
from src.errors import DefinitionError
from src.paths import resolve_dict, set_path


async def handle_assign(state, frame, context, interpreter) -> dict[str, Any] | None:
    """Execute assignment operations via the operations registry.

    For each key in ``state.set``, either dispatches the named operation
    through ``REGISTRY.execute()`` (when the value is a dict with an
    ``op`` key) or resolves the value directly via ``resolve_dict``.
    Results are written into frame variables with ``set_path``.

    Args:
        state: The ``AssignState`` model for the current step.
        frame: The active ``StackFrame`` (mutated: ``state_id``, ``vars``).
        context: Deterministic step context dict.
        interpreter: The ``SFSMInterpreter`` instance (used for logging).

    Returns:
        ``None`` to continue the interpreter loop.

    Raises:
        DefinitionError: If an operation raises ``ValueError`` (e.g.
            invalid append target).
    """
    for k, v in state.set.items():
        if isinstance(v, dict) and "op" in v:
            try:
                result = REGISTRY.execute(v["op"], v, context)
            except ValueError as exc:
                raise DefinitionError(str(exc)) from exc
            if result is not None:
                set_path(frame.vars, k, result)
        else:
            set_path(frame.vars, k, resolve_dict(v, context))
        workflow.logger.info(f"Assigned '{k}' = {frame.vars.get(k)}")
    frame.state_id = state.next
    return None
