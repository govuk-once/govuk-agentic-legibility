"""Tests for local journey execution traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.src.workflow_executor.client import HttpExchange
from agents.src.workflow_executor.trace import JsonlTraceRecorder


def read_events(path: Path) -> list[dict[str, Any]]:
    """Read JSONL trace events from a file.

    Args:
        path: Trace file to read.

    Returns:
        Decoded trace events in file order.
    """
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_trace_recorder_appends_run_exchange_and_finish_events(tmp_path: Path) -> None:
    """A completed run is represented by ordered append-only events."""
    trace_path = tmp_path / "run.jsonl"
    recorder = JsonlTraceRecorder(
        trace_path,
        run_id="run-123",
        journey_id="change-driving-licence-address",
        consumer="json_cli",
    )

    recorder.record_exchange(
        HttpExchange(
            method="POST",
            path="/journeys/change-address/steps",
            request_body={"cursor": "[redacted]", "result": {"answer": True}},
            status_code=200,
            response_body={"status": "completed"},
            duration_ms=12.3456,
        )
    )
    recorder.record_finished({"status": "completed"})

    events = read_events(trace_path)
    assert [event["sequence"] for event in events] == [0, 1, 2]
    assert [event["type"] for event in events] == [
        "run_started",
        "http_exchange",
        "run_finished",
    ]
    assert {event["run_id"] for event in events} == {"run-123"}
    assert events[0]["trace_version"] == "1.5"
    assert events[1]["request"]["path"] == "/journeys/change-address/steps"
    assert events[1]["duration_ms"] == 12.346
    assert events[2]["terminal_status"] == "completed"


def test_trace_recorder_records_a_non_terminal_stop(tmp_path: Path) -> None:
    """A deliberately partial CLI run records why it stopped."""
    trace_path = tmp_path / "run.jsonl"
    recorder = JsonlTraceRecorder(
        trace_path,
        run_id="run-456",
        journey_id="change-driving-licence-address",
        consumer="json_cli",
    )

    recorder.record_stopped(
        {
            "status": "in_progress",
            "interaction": {"id": "enter_address_manually"},
        },
        reason="maximum_interactions_reached",
    )

    stopped = read_events(trace_path)[1]
    assert stopped["run_id"] == "run-456"
    assert stopped["sequence"] == 1
    assert stopped["type"] == "run_stopped"
    assert stopped["reason"] == "maximum_interactions_reached"
    assert stopped["status"] == "in_progress"
    assert stopped["interaction_id"] == "enter_address_manually"


def test_trace_recorder_creates_a_unique_file_in_requested_directory(
    tmp_path: Path,
) -> None:
    """The convenience constructor creates a local JSONL trace immediately."""
    recorder = JsonlTraceRecorder.create(
        tmp_path / "nested",
        journey_id="change-driving-licence-address",
        consumer="automated_fixture",
    )

    assert recorder.path.parent == tmp_path / "nested"
    assert recorder.path.suffix == ".jsonl"
    assert recorder.run_id
    assert "change-driving-licence-address" in recorder.path.name
    assert read_events(recorder.path)[0]["consumer"] == "automated_fixture"
    assert recorder.read_events() == read_events(recorder.path)


def test_trace_records_agent_proposal_review_without_treating_added_fields_as_edits(
    tmp_path: Path,
) -> None:
    """Only changes to proposed fields count as edits to the agent proposal."""
    recorder = JsonlTraceRecorder(
        tmp_path / "run.jsonl",
        run_id="run-agent",
        journey_id="change-driving-licence-address",
        consumer="agent_assisted_http_frontend",
    )

    recorder.record_proposal_reviewed(
        interaction_id="enter_address_manually",
        proposed_values={"address_line_1": "18 Station Road"},
        submitted_values={
            "address_line_1": "18 Station Road",
            "town_or_city": "Bristol",
        },
    )
    recorder.record_proposal_reviewed(
        interaction_id="enter_address_manually",
        proposed_values={"address_line_1": "18 Station Road"},
        submitted_values={"address_line_1": "81 Station Road"},
    )

    accepted, edited = read_events(recorder.path)[1:]
    assert accepted["changed"] is False
    assert accepted["changed_fields"] == []
    assert edited["changed"] is True
    assert edited["changed_fields"] == ["address_line_1"]


def test_trace_records_loaded_fixture_and_complete_conversation(tmp_path: Path) -> None:
    """A run records the exact fixed input used by UI or automated consumers."""
    recorder = JsonlTraceRecorder(
        tmp_path / "run.jsonl",
        run_id="run-fixture",
        journey_id="change-driving-licence-address",
        consumer="automated_fixture",
    )
    recorder.record_fixture_loaded(
        fixture_id="address-context",
        fixture_version="1",
        fixture_sha256="abc123",
        conversation=[{"role": "user", "content": "Use postcode lookup."}],
    )

    event = read_events(recorder.path)[1]
    assert event["type"] == "fixture_loaded"
    assert event["fixture_id"] == "address-context"
    assert event["conversation"][0]["content"] == "Use postcode lookup."


def test_trace_records_why_the_assistant_was_invoked(tmp_path: Path) -> None:
    """The trace distinguishes a new user message from a newly opened form."""
    recorder = JsonlTraceRecorder(
        tmp_path / "run.jsonl",
        run_id="run-trigger",
        journey_id="change-driving-licence-address",
        consumer="automated_fixture",
    )
    recorder.record_agent_invoked(
        model_id="test-model",
        prompt_id="test-prompt-v4",
        interaction={"id": "choose_address_entry_method"},
        conversation=[{"role": "user", "content": "Does this work for flats?"}],
        trigger={
            "type": "user_message_added",
            "message": "Does this work for flats?",
        },
    )

    invoked = read_events(recorder.path)[1]
    assert invoked["input"]["trigger"] == {
        "type": "user_message_added",
        "message": "Does this work for flats?",
    }


def test_trace_distinguishes_retrieved_and_ungrounded_journey_answers(
    tmp_path: Path,
) -> None:
    """Tool evidence is recorded independently from the model's answer action."""
    recorder = JsonlTraceRecorder(
        tmp_path / "run.jsonl",
        run_id="run-guidance",
        journey_id="change-driving-licence-address",
        consumer="automated_fixture",
    )
    recorder.record_agent_tool_requested(
        tool="list_journey_guidance",
        arguments={},
    )
    recorder.record_agent_tool_completed(
        tool="list_journey_guidance",
        arguments={},
        result={"version": "1", "topics": []},
    )
    recorder.record_answer_presented(
        interaction_id="choose_address_entry_method",
        answer="Prototype answer without a retrieved document.",
        retrieved_guidance=[],
    )

    events = read_events(recorder.path)
    assert [event["type"] for event in events[1:]] == [
        "agent_tool_requested",
        "agent_tool_completed",
        "answer_presented",
    ]
    assert events[-1]["grounded_in_retrieved_guidance"] is False


def test_trace_records_ordered_compound_agent_actions(tmp_path: Path) -> None:
    """One model response retains both semantic actions in their returned order."""
    recorder = JsonlTraceRecorder(
        tmp_path / "run.jsonl",
        run_id="run-compound",
        journey_id="change-driving-licence-address",
        consumer="automated_fixture",
    )
    recorder.record_agent_responded(
        model_id="test-model",
        actions=[
            {
                "type": "answer_journey_question",
                "values": {},
                "message": None,
                "answer": "Postcode lookup can be used for a flat.",
            },
            {
                "type": "propose_values",
                "values": {"use_postcode_lookup": True},
                "message": None,
                "answer": None,
            },
        ],
        retrieved_guidance=[],
        duration_ms=10.0,
    )

    responded = read_events(recorder.path)[1]
    assert [action["type"] for action in responded["actions"]] == [
        "answer_journey_question",
        "propose_values",
    ]
