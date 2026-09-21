"""Tests for capturing semantic evaluator checkpoints."""

import pytest

from evaluation.capture_checkpoint import validate_target


def checkpoint_at(process_id: str, state_id: str) -> dict[str, object]:
    """Build the small part of a captured checkpoint used by validation."""
    return {
        "current_state": {
            "process_id": process_id,
            "state_id": state_id,
        },
        "awaiting": {"state_id": state_id},
    }


def test_validate_target_accepts_matching_input_state() -> None:
    validate_target(
        checkpoint_at("section4_about_payment", "prompt_date_stopped_work"),
        expected_process="section4_about_payment",
        expected_state="prompt_date_stopped_work",
    )


def test_validate_target_rejects_wrong_state() -> None:
    with pytest.raises(ValueError, match="not at the scenario checkpoint"):
        validate_target(
            checkpoint_at("section4_about_payment", "prompt_payment_frequency"),
            expected_process="section4_about_payment",
            expected_state="prompt_date_stopped_work",
        )
