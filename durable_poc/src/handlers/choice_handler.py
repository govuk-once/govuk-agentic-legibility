"""ChoiceState handler — evaluates predicate rules and branches."""

from typing import Any

from temporalio import workflow

from src.predicates import evaluate


async def handle_choice(state, frame, context, interpreter) -> dict[str, Any] | None:
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
