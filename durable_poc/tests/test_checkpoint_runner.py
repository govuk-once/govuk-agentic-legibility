"""Tests for targeted durable evaluation checkpoint setup."""

from pathlib import Path

import pytest

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
CHECKPOINT_DIR = DURABLE_ROOT / "evaluation" / "checkpoints"
DEFINITION = DURABLE_ROOT / "dwp_ma1_schema.json"


def test_date_stopped_work_uses_captured_real_interpreter_state() -> None:
    scenario = load_document(SCENARIO_DIR / "date-stopped-work-natural-language.yaml")
    definition = load_document(DEFINITION)
    checkpoint = scenario["input"]["checkpoint"]

    state = build_checkpoint_state(definition, checkpoint, CHECKPOINT_DIR)

    assert len(state.frames) == 2
    assert state.frames[0].process_id == "main"
    assert state.frames[0].state_id == "summary_section4"
    assert state.frames[1].process_id == "section4_about_payment"
    assert state.frames[1].state_id == "prompt_date_stopped_work"
    assert state.frames[1].invoker_state == "invoke_section4_about_payment"
    assert state.frames[1].vars["reason_stopped_work"] == "pregnancy_sick_leave"
    assert state.frames[1].vars["input"]["is_baby_born"] is False
    assert state.frames[0].vars["section2_data"]["due_date"] == "01/11/2026"
    assert state.frames[0].vars["section3_data"]["worked_in_15th_week"] is True

    # The captured workflow is suspended inside InputState at step 53. A fresh
    # workflow starts immediately before re-executing that state, so it resumes
    # from 52 and recreates tkn_53 itself.
    assert state.step_counter == 52
    assert len(state.transcript) == 18


def test_baby_not_born_uses_captured_real_interpreter_state() -> None:
    scenario = load_document(SCENARIO_DIR / "baby-not-born.yaml")
    definition = load_document(DEFINITION)

    state = build_checkpoint_state(
        definition,
        scenario["input"]["checkpoint"],
        CHECKPOINT_DIR,
    )

    assert len(state.frames) == 2
    assert state.frames[0].process_id == "main"
    assert state.frames[0].state_id == "announce_section3"
    assert state.frames[1].process_id == "section2_about_baby"
    assert state.frames[1].state_id == "prompt_is_baby_born"
    assert state.frames[1].invoker_state == "invoke_section2_about_baby"
    assert state.frames[0].vars["section1_data"]["identity"]["first_name"] == "Jane"
    assert state.frames[1].vars["is_baby_born"] is None
    assert state.step_counter == 17


def test_checkpoint_id_is_required() -> None:
    definition = load_document(DEFINITION)

    with pytest.raises(ValueError, match="checkpoint.id"):
        build_checkpoint_state(
            definition,
            {
                "process_id": "section2_about_baby",
                "state_id": "prompt_is_baby_born",
            },
            CHECKPOINT_DIR,
        )


def test_date_stopped_work_fixture_uses_full_history_and_natural_language_turn(
) -> None:
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


def test_interpreter_rehydrates_captured_invoker_state() -> None:
    from src.interpreter import SFSMInterpreter
    from src.model import InvokeState, SFSMDefinition

    scenario = load_document(SCENARIO_DIR / "date-stopped-work-natural-language.yaml")
    definition_dict = load_document(DEFINITION)
    state = build_checkpoint_state(
        definition_dict,
        scenario["input"]["checkpoint"],
        CHECKPOINT_DIR,
    )

    interpreter = SFSMInterpreter()
    interpreter.definition = SFSMDefinition.model_validate(definition_dict)
    interpreter.state = state
    interpreter._rehydrate_initial_state_invokers()

    invoker = interpreter.state.frames[1].invoker_state
    assert isinstance(invoker, InvokeState)
    assert invoker.process == "section4_about_payment"
    assert invoker.assign == "section4_data"
    assert invoker.next == "summary_section4"
