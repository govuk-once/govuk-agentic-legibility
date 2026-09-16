"""Tests for targeted durable evaluation checkpoint setup."""

from pathlib import Path

from evaluation.checkpoint_runner import agent_input, build_checkpoint_state
from evaluation.scenario_case import load_document, load_scenario_case

DURABLE_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = DURABLE_ROOT / "evaluation" / "scenarios" / "maternity_allowance"
DEFINITION = DURABLE_ROOT / "dwp_ma1_schema.json"


def test_compact_case_reference_resolves_colocated_inputs() -> None:
    scenario_case = load_scenario_case(
        Path("maternity_allowance/work_status_fixed_term_contract_ended")
    )

    assert scenario_case.scenario_path == (
        SCENARIO_DIR / "work_status_fixed_term_contract_ended" / "scenario.yaml"
    ).resolve()
    assert scenario_case.conversation_path.name == "conversation.json"
    assert scenario_case.checkpoint_path.name == "checkpoint.json"
    assert scenario_case.scenario["id"] == "ma-work-status-fixed-term-contract-ended"
    assert "input" not in scenario_case.scenario
    assert scenario_case.target == (
        "section4_about_payment",
        "prompt_reason_stopped_work",
    )


def test_date_stopped_work_uses_captured_real_interpreter_state() -> None:
    scenario_case = load_scenario_case(
        Path("maternity_allowance/date_stopped_work_natural_language")
    )
    definition = load_document(DEFINITION)

    state = build_checkpoint_state(definition, scenario_case.checkpoint)

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
    scenario_case = load_scenario_case(Path("maternity_allowance/baby_not_born"))
    definition = load_document(DEFINITION)

    state = build_checkpoint_state(definition, scenario_case.checkpoint)

    assert len(state.frames) == 2
    assert state.frames[0].process_id == "main"
    assert state.frames[0].state_id == "announce_section3"
    assert state.frames[1].process_id == "section2_about_baby"
    assert state.frames[1].state_id == "prompt_is_baby_born"
    assert state.frames[1].invoker_state == "invoke_section2_about_baby"
    assert state.frames[0].vars["section1_data"]["identity"]["first_name"] == "Jane"
    assert state.frames[1].vars["is_baby_born"] is None
    assert state.step_counter == 17


def test_date_stopped_work_fixture_uses_full_history_and_natural_language_turn() -> None:
    scenario_case = load_scenario_case(
        Path("maternity_allowance/date_stopped_work_natural_language")
    )
    definition = load_document(DEFINITION)
    prompt = definition["processes"]["section4_about_payment"]["states"][
        "prompt_date_stopped_work"
    ]["prompt"]

    history, current_user_message = agent_input(scenario_case.conversation, prompt)

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

    scenario_case = load_scenario_case(
        Path("maternity_allowance/date_stopped_work_natural_language")
    )
    definition_dict = load_document(DEFINITION)
    state = build_checkpoint_state(definition_dict, scenario_case.checkpoint)

    interpreter = SFSMInterpreter()
    interpreter.definition = SFSMDefinition.model_validate(definition_dict)
    interpreter.state = state
    interpreter._rehydrate_initial_state_invokers()

    invoker = interpreter.state.frames[1].invoker_state
    assert isinstance(invoker, InvokeState)
    assert invoker.process == "section4_about_payment"
    assert invoker.assign == "section4_data"
    assert invoker.next == "summary_section4"
