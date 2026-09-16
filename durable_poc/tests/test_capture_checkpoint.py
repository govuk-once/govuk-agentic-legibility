"""Tests for capturing semantic evaluator checkpoints."""

from pathlib import Path

import pytest

import evaluation.capture_checkpoint as capture_checkpoint
import evaluation.scenario_case as scenario_case
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


def test_new_case_reference_resolves_before_scenario_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_root = tmp_path / "scenarios"
    monkeypatch.setattr(
        capture_checkpoint, "DEFAULT_SCENARIO_ROOT", scenario_root
    )

    monkeypatch.setattr(
        scenario_case, "DEFAULT_SCENARIO_ROOT", scenario_root
    )
    checkpoint_path, process_id, state_id = (
        capture_checkpoint.scenario_capture_target(
            Path("maternity_allowance/claim_start_date_today")
        )
    )

    assert checkpoint_path == (
        scenario_root
        / "maternity_allowance"
        / "claim_start_date_today"
        / "checkpoint.json"
    ).resolve()
    assert process_id is None
    assert state_id is None
    assert not checkpoint_path.parent.exists()


def test_existing_checkpoint_validates_target_without_scenario(
    tmp_path: Path,
) -> None:
    case_directory = tmp_path / "claim_start_date_today"
    case_directory.mkdir()
    (case_directory / "checkpoint.json").write_text(
        """{
  \"current_state\": {
    \"process_id\": \"section4_about_payment\",
    \"state_id\": \"prompt_claim_start_date\"
  }
}
""",
        encoding="utf-8",
    )

    checkpoint_path, process_id, state_id = (
        capture_checkpoint.scenario_capture_target(case_directory)
    )

    assert checkpoint_path == case_directory / "checkpoint.json"
    assert process_id == "section4_about_payment"
    assert state_id == "prompt_claim_start_date"
