"""ChoiceState handler — evaluates predicate rules and branches."""

from typing import Any

from temporalio import workflow

from src.predicates import evaluate


async def handle_choice(state, frame, context, interpreter) -> dict[str, Any] | None:
    """Evaluate predicate rules and branch to the first matching transition.

    Iterates ``state.rules`` in order, evaluating each ``rule.when``
    condition against *context* via ``predicates.evaluate()``.  The first
    rule that evaluates to ``True`` determines the next state.  If no rule
    matches, execution falls through to ``state.default``.

    Args:
        state: The ``ChoiceState`` model for the current step.
        frame: The active ``StackFrame`` (mutated: ``state_id``).
        context: Deterministic step context dict.
        interpreter: The ``SFSMInterpreter`` instance (used for logging).

    Returns:
        ``None`` to continue the interpreter loop.
    """
    matched = False
    for idx, rule in enumerate(state.rules):
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
            f"No rules matched. Fallback to default '{state.default}'"
        )
        frame.state_id = state.default
    return None
