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
    assert events[0]["trace_version"] == "1.0"
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
    assert "change-driving-licence-address" in recorder.path.name
    assert read_events(recorder.path)[0]["consumer"] == "automated_fixture"
