"""Tests for end-to-end scenario execution."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agents.src.scenario_evaluation.run import (
    _automatic_user_result,
    _latest_proposed_values,
    run_scenario_file,
)


class FakeJourneyApplication:
    """Small implementation adapter used by runner tests."""

    def __init__(self) -> None:
        self.index = 0
        self.submissions: list[dict[str, Any]] = []
        self.responses = [
            _run_response("choose_address_entry_method"),
            _run_response("enter_address_manually"),
            _confirmation_response("confirm_new_address"),
            {
                "run_id": "run-123",
                "status": "completed",
                "terminal": True,
                "interaction": None,
            },
        ]

    def start(self, journey_id: str, fixture_id: str) -> dict[str, Any]:
        """Return the first interaction."""
        assert journey_id == "change-driving-licence-address"
        assert fixture_id == "fixture-one"
        return self.responses[0]

    def submit(
        self,
        run_id: str,
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Record the submitted result and return the next interaction."""
        assert run_id == "run-123"
        self.submissions.append(dict(result))
        self.index += 1
        return self.responses[self.index]

    def trace(self, run_id: str) -> list[dict[str, Any]]:
        """Return proposals available up to the active interaction."""
        assert run_id == "run-123"
        events: list[dict[str, Any]] = [
            {"type": "run_started", "run_id": "run-123", "trace_version": "1.5"},
            {
                "type": "fixture_loaded",
                "fixture_id": "fixture-one",
                "fixture_version": "1",
            },
        ]
        events.extend(
            _proposal("choose_address_entry_method", {"use_postcode_lookup": False})
        )
        if self.index >= 1:
            events.extend(
                _proposal(
                    "enter_address_manually",
                    {
                        "address_line_1": "18 Station Road",
                        "town_or_city": "Bristol",
                        "postcode": "BS1 3AB",
                    },
                )
            )
        if self.index >= 3:
            events.append({"type": "run_finished", "terminal_status": "completed"})
        return events


def test_runner_accepts_proposals_but_confirms_deterministically(
    tmp_path: Path,
) -> None:
    """The harness progresses using proposals without delegating confirmation."""
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(_scenario_yaml(), encoding="utf-8")
    client = FakeJourneyApplication()

    result = run_scenario_file(
        scenario_path,
        client,
        tmp_path / "runs",
        converter=_passing_converter,
    )

    assert result.passed
    assert client.submissions == [
        {"use_postcode_lookup": False},
        {
            "address_line_1": "18 Station Road",
            "town_or_city": "Bristol",
            "postcode": "BS1 3AB",
        },
        {"confirmed": True},
    ]
    assert result.raw_trace_path is not None
    assert '"type":"run_finished"' in result.raw_trace_path.read_text()


def test_confirmation_is_derived_from_service_semantics_not_interaction_id() -> None:
    """Confirmation does not depend on a journey-specific step name."""
    run = _confirmation_response("review-something-else")

    assert _automatic_user_result(run) == {"confirmed": True}


def test_missing_proposal_does_not_fall_back_to_expected_values(tmp_path: Path) -> None:
    """Expected scenario values cannot be used to help a failing implementation."""
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(_scenario_yaml(), encoding="utf-8")
    client = FakeJourneyApplication()
    client.trace = lambda _run_id: []  # type: ignore[method-assign]

    result = run_scenario_file(
        scenario_path,
        client,
        tmp_path / "runs",
        converter=_incomplete_converter,
    )

    assert not result.passed
    assert result.execution_error is not None
    assert "No propose_values action" in result.execution_error
    assert client.submissions == []


def test_proposal_lookup_is_scoped_to_current_interaction() -> None:
    """A proposal from an earlier service interaction is not reused later."""
    events = [
        *_proposal("earlier", {"value": "old"}),
        *_proposal("current", {"value": "right"}),
    ]

    values, error = _latest_proposed_values(events, "current")

    assert error is None
    assert values == {"value": "right"}


def _run_response(interaction_id: str) -> dict[str, Any]:
    return {
        "run_id": "run-123",
        "status": "in_progress",
        "terminal": False,
        "interaction": {"id": interaction_id},
    }


def _confirmation_response(interaction_id: str) -> dict[str, Any]:
    return {
        "run_id": "run-123",
        "status": "ready_for_confirmation",
        "terminal": False,
        "interaction": {
            "id": interaction_id,
            "input_schema": {
                "type": "object",
                "properties": {"confirmed": {"type": "boolean"}},
                "required": ["confirmed"],
            },
        },
    }


def _proposal(
    interaction_id: str,
    values: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "type": "agent_invoked",
            "input": {"interaction": {"id": interaction_id}},
        },
        {
            "type": "agent_responded",
            "actions": [{"type": "propose_values", "values": dict(values)}],
        },
    ]


def _passing_converter(_raw_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "trace.yaml"
    path.write_text(_common_trace(status="completed"), encoding="utf-8")
    return path


def _incomplete_converter(_raw_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "trace.yaml"
    path.write_text(_common_trace(status="incomplete"), encoding="utf-8")
    return path


def _scenario_yaml() -> str:
    return """\
schema_version: "0.1"
id: "manual-entry"
journey_id: "change-driving-licence-address"
input:
  conversation_fixture:
    id: "fixture-one"
    version: "1"
expected:
  assistance:
    choose_address_entry_method:
      type: "propose_values"
      values:
        use_postcode_lookup: false
    enter_address_manually:
      type: "propose_values"
      values:
        address_line_1: "18 Station Road"
        town_or_city: "Bristol"
        postcode: "BS1 3AB"
  journey:
    branch: "manual_entry"
    final:
      status: "completed"
"""


def _common_trace(*, status: str) -> str:
    finished = "" if status != "completed" else """
  - type: "journey_finished"
    status: "completed"
"""
    return f"""\
schema_version: "0.1"
source_trace: "raw.jsonl"
run:
  id: "run-123"
  journey_id: "change-driving-licence-address"
  implementation: "test"
  status: "{status}"
initial_context:
  conversation_fixture:
    id: "fixture-one"
    version: "1"
    sha256: "abc"
events:
  - type: "interaction_available"
    interaction_id: "choose_address_entry_method"
  - type: "values_proposed"
    interaction_id: "choose_address_entry_method"
    values:
      use_postcode_lookup: false
  - type: "interaction_available"
    interaction_id: "enter_address_manually"
  - type: "values_proposed"
    interaction_id: "enter_address_manually"
    values:
      address_line_1: "18 Station Road"
      town_or_city: "Bristol"
      postcode: "BS1 3AB"
{finished}"""
