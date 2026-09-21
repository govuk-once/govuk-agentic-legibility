"""Tests for targeted durable evaluation checkpoint setup."""

from pathlib import Path

from evaluation.checkpoint_runner import (
    agent_input,
    build_checkpoint_state,
    load_document,
)

DURABLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DURABLE_ROOT.parent
SCENARIO_DIR = (
    REPO_ROOT / "agents" / "evaluation" / "scenarios" / "maternity-allowance"
)
FIXTURE_DIR = REPO_ROOT / "agents" / "src" / "evaluation" / "fixtures"
DEFINITION = DURABLE_ROOT / "dwp_ma1_schema.json"


def test_date_stopped_work_checkpoint_contains_required_prior_state() -> None:
    scenario = load_document(SCENARIO_DIR / "date-stopped-work-natural-language.yaml")
    definition = load_document(DEFINITION)

    state = build_checkpoint_state(definition, scenario["input"]["checkpoint"])
    frame = state.frames[0]

    assert frame.process_id == "section4_about_payment"
    assert frame.state_id == "prompt_date_stopped_work"
    assert frame.vars["reason_stopped_work"] == "pregnancy_sick_leave"
    assert frame.vars["input"]["is_baby_born"] is False
    assert (
        frame.vars["input"]["calculated_dates"]["smp_qualifying_week"]
        == "27/08/2026"
    )


def test_date_stopped_work_fixture_uses_full_history_and_natural_language_turn() -> None:
    fixture = load_document(
        FIXTURE_DIR / "ma_date_stopped_work_natural_language.json"
    )
    definition = load_document(DEFINITION)
    prompt = definition["processes"]["section4_about_payment"]["states"][
        "prompt_date_stopped_work"
    ]["prompt"]

    history, current_user_message = agent_input(fixture, prompt)

    assert current_user_message == "3 September 2026."
    history_text = "\n".join(
        block["text"] for item in history for block in item["content"]
    )
    assert "I want to apply for Maternity Allowance." in history_text
    assert "No, I'm still pregnant." in history_text
    assert "I'm off work with a pregnancy-related illness." in history_text
    assert prompt not in history_text
