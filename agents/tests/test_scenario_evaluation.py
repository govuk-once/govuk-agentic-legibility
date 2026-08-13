"""Tests for implementation-independent scenario evaluation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from agents.src.scenario_evaluation.__main__ import main as cli_main
from agents.src.scenario_evaluation.evaluator import (
    EvaluationInputError,
    evaluate_common_trace,
    load_document,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_SCENARIO_PATH = (
    REPO_ROOT
    / "agents/evaluation/scenarios/change-driving-licence-address/manual-entry.yaml"
)
COMPLIANT_MANUAL_TRACE_PATH = (
    REPO_ROOT
    / "agents/tests/fixtures/scenario_evaluation/manual-entry-compliant.common.yaml"
)
HISTORICAL_MANUAL_TRACE_PATH = (
    REPO_ROOT
    / "agents/examples/common_trace/expected/"
    "manual-entry-from-conversation-history.common.yaml"
)


def manual_scenario() -> dict[str, Any]:
    """Return a complete manual-entry scenario."""
    return {
        "schema_version": "0.1",
        "id": "manual-entry",
        "journey_id": "change-driving-licence-address",
        "input": {
            "conversation_fixture": {
                "id": "complete-address-manual-entry",
                "version": "1",
            }
        },
        "expected": {
            "assistance": {
                "choose_address_entry_method": {
                    "type": "propose_values",
                    "values": {"use_postcode_lookup": False},
                },
                "enter_address_manually": {
                    "type": "propose_values",
                    "values": {
                        "address_line_1": "Flat 4",
                        "address_line_2": "81 Station Road",
                        "town_or_city": "Bristol",
                        "postcode": "BS1 3AB",
                    },
                },
            },
            "journey": {
                "branch": "manual_entry",
                "final": {
                    "status": "completed",
                    "result": {
                        "new_address": {
                            "address_line_1": "Flat 4",
                            "address_line_2": "81 Station Road",
                            "town_or_city": "Bristol",
                            "postcode": "BS1 3AB",
                        }
                    },
                },
            },
        },
        "evaluation": {
            "accepted_equivalence_rules": [
                {
                    "type": "unordered_text_components",
                    "target": "expected.assistance.enter_address_manually.values",
                    "paths": ["address_line_1", "address_line_2"],
                },
                {
                    "type": "unordered_text_components",
                    "target": "expected.journey.final.result",
                    "paths": [
                        "new_address.address_line_1",
                        "new_address.address_line_2",
                    ],
                },
            ]
        },
    }


def manual_trace() -> dict[str, Any]:
    """Return a matching common semantic trace."""
    return {
        "schema_version": "0.1",
        "source_trace": "manual.jsonl",
        "run": {
            "id": "run-1",
            "journey_id": "change-driving-licence-address",
            "implementation": "example",
            "status": "completed",
        },
        "initial_context": {
            "conversation_fixture": {
                "id": "complete-address-manual-entry",
                "version": "1",
                "sha256": "abc",
            }
        },
        "events": [
            {
                "type": "interaction_available",
                "interaction_id": "choose_address_entry_method",
            },
            {
                "type": "values_proposed",
                "interaction_id": "choose_address_entry_method",
                "values": {"use_postcode_lookup": False},
            },
            {
                "type": "values_submitted",
                "interaction_id": "choose_address_entry_method",
                "values": {"use_postcode_lookup": False},
            },
            {
                "type": "interaction_available",
                "interaction_id": "enter_address_manually",
            },
            {
                "type": "values_proposed",
                "interaction_id": "enter_address_manually",
                "values": {
                    "address_line_1": "Flat 4",
                    "address_line_2": "81 Station Road",
                    "town_or_city": "Bristol",
                    "postcode": "BS1 3AB",
                },
            },
            {
                "type": "values_submitted",
                "interaction_id": "enter_address_manually",
                "values": {
                    "address_line_1": "Flat 4",
                    "address_line_2": "81 Station Road",
                    "town_or_city": "Bristol",
                    "postcode": "BS1 3AB",
                },
            },
            {
                "type": "journey_finished",
                "status": "completed",
                "result": {
                    "new_address": {
                        "address_line_1": "Flat 4",
                        "address_line_2": "81 Station Road",
                        "town_or_city": "Bristol",
                        "postcode": "BS1 3AB",
                    }
                },
            },
        ],
    }


def _proposal(trace: dict[str, Any], interaction_id: str) -> dict[str, Any]:
    return next(
        event
        for event in trace["events"]
        if event.get("type") == "values_proposed"
        and event.get("interaction_id") == interaction_id
    )


def _finished(trace: dict[str, Any]) -> dict[str, Any]:
    return next(
        event for event in trace["events"] if event.get("type") == "journey_finished"
    )


def test_matching_trace_passes() -> None:
    """A trace satisfying all scenario expectations passes."""
    result = evaluate_common_trace(manual_scenario(), manual_trace())

    assert result.passed
    assert result.issues == ()


def test_equivalent_address_line_representations_pass() -> None:
    """Configured address lines may move between fields without changing meaning."""
    trace = manual_trace()
    proposed = _proposal(trace, "enter_address_manually")
    proposed["values"]["address_line_1"] = "Flat 4, 81 Station Road"
    proposed["values"]["address_line_2"] = None

    final_address = _finished(trace)["result"]["new_address"]
    final_address["address_line_1"] = "81"
    final_address["address_line_2"] = "Station Road, Flat 4"

    result = evaluate_common_trace(manual_scenario(), trace)

    assert result.passed


def test_equivalence_rule_does_not_hide_other_field_mismatch() -> None:
    """Equivalence relaxes only the paths explicitly named by the scenario."""
    trace = manual_trace()
    proposed = _proposal(trace, "enter_address_manually")
    proposed["values"]["town_or_city"] = "Bath"

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any(
        issue.path == "expected.assistance.enter_address_manually.values"
        for issue in result.issues
    )


def test_missing_address_component_still_fails_equivalence() -> None:
    """Moving text is allowed, but dropping expected address content is not."""
    trace = manual_trace()
    proposed = _proposal(trace, "enter_address_manually")
    proposed["values"]["address_line_1"] = "Flat 4"
    proposed["values"]["address_line_2"] = "Station Road"

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any(
        issue.path == "expected.assistance.enter_address_manually.values"
        for issue in result.issues
    )


def test_missing_expected_proposal_fails() -> None:
    """An expected proposal must be present exactly once."""
    trace = manual_trace()
    trace["events"] = [
        event
        for event in trace["events"]
        if not (
            event.get("type") == "values_proposed"
            and event.get("interaction_id") == "enter_address_manually"
        )
    ]

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any("observed 0" in issue.message for issue in result.issues)


def test_unexpected_proposal_fails_when_assistance_is_evaluated() -> None:
    """A present assistance section is closed-world and rejects extra assistance."""
    trace = manual_trace()
    trace["events"].insert(
        -1,
        {
            "type": "values_proposed",
            "interaction_id": "confirm_new_address",
            "values": {"confirmed": True},
        },
    )

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any(
        issue.path == "expected.assistance.confirm_new_address"
        for issue in result.issues
    )


def test_branch_only_scenario_ignores_other_dimensions() -> None:
    """Omitted expectations are not scored."""
    scenario = deepcopy(manual_scenario())
    scenario["expected"] = {"journey": {"branch": "manual_entry"}}
    scenario.pop("evaluation")

    trace = manual_trace()
    trace["events"].insert(
        -1,
        {
            "type": "values_proposed",
            "interaction_id": "confirm_new_address",
            "values": {"confirmed": True},
        },
    )
    trace["events"].insert(
        -1,
        {
            "type": "assistance_failed",
            "interaction_id": "enter_address_manually",
        },
    )
    trace["run"]["status"] = "incomplete"
    _finished(trace)["status"] = "incomplete"
    _finished(trace)["result"] = {"unexpected": True}

    result = evaluate_common_trace(scenario, trace)

    assert result.passed


def test_empty_assistance_section_rejects_any_proposal() -> None:
    """An explicitly empty assistance section means no assistance is expected."""
    scenario = deepcopy(manual_scenario())
    scenario["expected"] = {"assistance": {}}
    scenario.pop("evaluation")

    result = evaluate_common_trace(scenario, manual_trace())

    assert not result.passed
    assert any("unexpected values_proposed" in issue.message for issue in result.issues)


def test_final_status_only_ignores_result() -> None:
    """A scenario may evaluate completion without constraining the final result."""
    scenario = deepcopy(manual_scenario())
    scenario["expected"] = {"journey": {"final": {"status": "completed"}}}
    scenario.pop("evaluation")
    trace = manual_trace()
    _finished(trace)["result"] = {"anything": "is allowed"}

    result = evaluate_common_trace(scenario, trace)

    assert result.passed


def test_final_result_only_ignores_status() -> None:
    """A scenario may evaluate a terminal result without constraining status."""
    scenario = deepcopy(manual_scenario())
    expected_result = scenario["expected"]["journey"]["final"]["result"]
    scenario["expected"] = {
        "journey": {"final": {"result": expected_result}},
    }
    trace = manual_trace()
    trace["run"]["status"] = "another-status"
    _finished(trace)["status"] = "another-status"

    result = evaluate_common_trace(scenario, trace)

    assert result.passed


def test_wrong_branch_fails_even_when_other_dimensions_are_omitted() -> None:
    """Branch evidence can be evaluated independently."""
    scenario = deepcopy(manual_scenario())
    scenario["expected"] = {"journey": {"branch": "manual_entry"}}
    scenario.pop("evaluation")
    trace = manual_trace()
    trace["events"] = [
        event
        for event in trace["events"]
        if not (
            event.get("type") == "interaction_available"
            and event.get("interaction_id") == "enter_address_manually"
        )
    ]
    trace["events"].insert(
        3,
        {
            "type": "interaction_available",
            "interaction_id": "find_address_by_postcode",
        },
    )

    result = evaluate_common_trace(scenario, trace)

    assert not result.passed
    assert any(issue.path == "expected.journey.branch" for issue in result.issues)


def test_wrong_terminal_result_fails() -> None:
    """The service's final result is compared independently of proposals."""
    trace = manual_trace()
    _finished(trace)["result"]["new_address"]["postcode"] = "SW1A 1AA"

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any(issue.path == "expected.journey.final.result" for issue in result.issues)


def test_fixture_identity_must_match() -> None:
    """A trace from another fixture cannot accidentally satisfy the scenario."""
    trace = manual_trace()
    trace["initial_context"]["conversation_fixture"]["id"] = "another-fixture"

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any(
        issue.path == "input.conversation_fixture.id" for issue in result.issues
    )


def test_assistance_failure_fails_when_assistance_is_evaluated() -> None:
    """A technical failure invalidates an assistance expectation."""
    trace = manual_trace()
    trace["events"].insert(
        -1,
        {
            "type": "assistance_failed",
            "interaction_id": "enter_address_manually",
        },
    )

    result = evaluate_common_trace(manual_scenario(), trace)

    assert not result.passed
    assert any("assistance failed" in issue.message for issue in result.issues)


def test_unsupported_branch_is_configuration_error() -> None:
    """Unknown semantic branch names are not silently ignored."""
    scenario = deepcopy(manual_scenario())
    scenario["expected"]["journey"]["branch"] = "unknown"

    with pytest.raises(EvaluationInputError, match="No branch observation rule"):
        evaluate_common_trace(scenario, manual_trace())


def test_unsupported_equivalence_rule_is_configuration_error() -> None:
    """Unknown equivalence semantics are rejected rather than guessed."""
    scenario = deepcopy(manual_scenario())
    scenario["evaluation"]["accepted_equivalence_rules"][0]["type"] = "fuzzy"

    with pytest.raises(EvaluationInputError, match="Unsupported equivalence rule"):
        evaluate_common_trace(scenario, manual_trace())


def test_committed_manual_scenario_accepts_compliant_trace_fixture() -> None:
    """The real scenario accepts a deliberately compliant common trace fixture."""
    result = evaluate_common_trace(
        load_document(MANUAL_SCENARIO_PATH),
        load_document(COMPLIANT_MANUAL_TRACE_PATH),
    )

    assert result.passed, [f"{issue.path}: {issue.message}" for issue in result.issues]


def test_historical_manual_trace_rejects_agent_confirmation_proposal() -> None:
    """The historical trace is valid common trace but intentionally non-compliant."""
    result = evaluate_common_trace(
        load_document(MANUAL_SCENARIO_PATH),
        load_document(HISTORICAL_MANUAL_TRACE_PATH),
    )

    assert not result.passed
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.path == "expected.assistance.confirm_new_address"
    assert "unexpected values_proposed event" in issue.message
    assert "confirmed" in issue.message


def test_cli_expected_failure_is_reported_as_passing_assertion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A known evaluator rejection can be asserted without a failing shell status."""
    exit_code = cli_main(
        [
            str(MANUAL_SCENARIO_PATH),
            str(HISTORICAL_MANUAL_TRACE_PATH),
            "--expect",
            "fail",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.startswith("PASS manual-entry: evaluation failed as expected:")
    assert "expected.assistance.confirm_new_address" in output
    assert "\nFAIL " not in output


def test_cli_expected_failure_fails_if_trace_unexpectedly_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An expected-failure assertion catches a regression that starts passing."""
    exit_code = cli_main(
        [
            str(MANUAL_SCENARIO_PATH),
            str(COMPLIANT_MANUAL_TRACE_PATH),
            "--expect",
            "fail",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "expected evaluation to fail, but it passed" in output
