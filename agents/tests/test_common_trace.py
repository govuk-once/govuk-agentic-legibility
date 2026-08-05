"""Tests for conversion from raw JSONL events to common journey traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from agents.src.common_trace.convert import (
    JsonObject,
    convert_paths,
    convert_raw_trace,
    dump_yaml,
)


def run_started(*, consumer: str = "agent_assisted_http_frontend") -> JsonObject:
    """Build the first event required by every raw trace."""
    return {
        "run_id": "run-1",
        "sequence": 0,
        "timestamp": "2026-08-01T18:00:00.000Z",
        "type": "run_started",
        "trace_version": "1.5",
        "journey_id": "change-driving-licence-address",
        "consumer": consumer,
    }


def interaction_response(sequence: int, interaction_id: str) -> JsonObject:
    """Build a raw HTTP event exposing one service interaction."""
    return {
        "run_id": "run-1",
        "sequence": sequence,
        "timestamp": "2026-08-01T18:00:00.000Z",
        "type": "http_exchange",
        "request": {"method": "POST", "path": "/journey", "body": None},
        "response": {
            "status_code": 200,
            "body": {
                "status": "in_progress",
                "continuation_token": "secret",
                "interaction": {"id": interaction_id},
                "next_action": {"method": "POST", "path": "/next"},
            },
        },
        "duration_ms": 1,
    }


def test_converts_positive_behaviour_without_agent_control_details() -> None:
    """The common trace records outcomes rather than invocation mechanics."""
    raw_events: list[JsonObject] = [
        run_started(),
        {
            "run_id": "run-1",
            "sequence": 1,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "fixture_loaded",
            "fixture_id": "complete-address-manual-entry",
            "fixture_version": "1",
            "fixture_sha256": "abc123",
            "conversation": [
                {"role": "user", "content": "Use 81 Station Road."}
            ],
        },
        interaction_response(2, "choose_address_entry_method"),
        {
            "run_id": "run-1",
            "sequence": 3,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_invoked",
            "model_id": "model",
            "prompt_id": "prompt",
            "input": {
                "trigger": {"type": "interaction_opened"},
                "conversation": [],
                "interaction": {"id": "choose_address_entry_method"},
            },
        },
        {
            "run_id": "run-1",
            "sequence": 4,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_responded",
            "model_id": "model",
            "actions": [
                {
                    "type": "propose_values",
                    "values": {"use_postcode_lookup": False},
                }
            ],
            "retrieved_guidance": [],
            "duration_ms": 1,
        },
        {
            "run_id": "run-1",
            "sequence": 5,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "user_message",
            "interaction_id": "choose_address_entry_method",
            "message": "Does postcode lookup work for flats?",
        },
        {
            "run_id": "run-1",
            "sequence": 6,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_invoked",
            "model_id": "model",
            "prompt_id": "prompt",
            "input": {
                "trigger": {"type": "user_message_added"},
                "conversation": [],
                "interaction": {"id": "choose_address_entry_method"},
            },
        },
        {
            "run_id": "run-1",
            "sequence": 7,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_tool_completed",
            "tool": "get_journey_guidance",
            "arguments": {"topic_id": "postcode-lookup-for-flats"},
            "result": {"id": "postcode-lookup-for-flats", "version": "1"},
        },
        {
            "run_id": "run-1",
            "sequence": 8,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_responded",
            "model_id": "model",
            "actions": [
                {"type": "answer_journey_question", "answer": "Yes."},
                {
                    "type": "propose_values",
                    "values": {"use_postcode_lookup": True},
                },
            ],
            "retrieved_guidance": [],
            "duration_ms": 1,
        },
        {
            "run_id": "run-1",
            "sequence": 9,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "answer_presented",
            "interaction_id": "choose_address_entry_method",
            "answer": "Yes.",
            "retrieved_guidance": [],
            "grounded_in_retrieved_guidance": True,
        },
        {
            "run_id": "run-1",
            "sequence": 10,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "proposal_reviewed",
            "interaction_id": "choose_address_entry_method",
            "proposed_values": {"use_postcode_lookup": True},
            "submitted_values": {"use_postcode_lookup": True},
            "changed": False,
            "changed_fields": [],
        },
        {
            "run_id": "run-1",
            "sequence": 11,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "result_submitted",
            "interaction_id": "choose_address_entry_method",
            "source": "agent_proposal_review",
            "result": {"use_postcode_lookup": True},
        },
    ]

    common = convert_raw_trace(raw_events, source_trace="raw.jsonl")

    assert common["initial_context"] == {
        "conversation_fixture": {
            "id": "complete-address-manual-entry",
            "version": "1",
            "sha256": "abc123",
        }
    }
    assert common["events"] == [
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
            "type": "user_message",
            "content": "Does postcode lookup work for flats?",
            "interaction_id": "choose_address_entry_method",
        },
        {
            "type": "guidance_retrieved",
            "interaction_id": "choose_address_entry_method",
            "source": {"id": "postcode-lookup-for-flats", "version": "1"},
        },
        {
            "type": "values_proposed",
            "interaction_id": "choose_address_entry_method",
            "values": {"use_postcode_lookup": True},
        },
        {
            "type": "answer_presented",
            "interaction_id": "choose_address_entry_method",
        },
        {
            "type": "values_submitted",
            "values": {"use_postcode_lookup": True},
            "interaction_id": "choose_address_entry_method",
        },
    ]


def test_no_safe_suggestion_produces_no_common_outcome() -> None:
    """A safe absence of proposals is represented by no proposal event."""
    raw_events: list[JsonObject] = [
        run_started(),
        interaction_response(1, "enter_address_manually"),
        {
            "run_id": "run-1",
            "sequence": 2,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_invoked",
            "model_id": "model",
            "prompt_id": "prompt",
            "input": {"interaction": {"id": "enter_address_manually"}},
        },
        {
            "run_id": "run-1",
            "sequence": 3,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_responded",
            "model_id": "model",
            "action": {"type": "no_safe_suggestion", "message": None},
            "duration_ms": 1,
        },
    ]

    common = convert_raw_trace(raw_events, source_trace="abandoned.jsonl")

    assert common["run"] == {
        "id": "run-1",
        "journey_id": "change-driving-licence-address",
        "implementation": "agent_assisted_http_frontend",
        "status": "incomplete",
    }
    assert common["events"] == [
        {
            "type": "interaction_available",
            "interaction_id": "enter_address_manually",
        }
    ]


def test_maps_terminal_response_and_old_singular_proposal() -> None:
    """Historical singular actions and completed journeys remain convertible."""
    raw_events: list[JsonObject] = [
        run_started(consumer="http_frontend"),
        interaction_response(1, "confirm_new_address"),
        {
            "run_id": "run-1",
            "sequence": 2,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_invoked",
            "model_id": "model",
            "prompt_id": "prompt",
            "input": {"interaction": {"id": "confirm_new_address"}},
        },
        {
            "run_id": "run-1",
            "sequence": 3,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "agent_responded",
            "model_id": "model",
            "action": {
                "type": "propose_values",
                "values": {"confirmed": True},
            },
            "duration_ms": 1,
        },
        {
            "run_id": "run-1",
            "sequence": 4,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "http_exchange",
            "request": {"method": "POST", "path": "/confirm", "body": None},
            "response": {
                "status_code": 200,
                "body": {
                    "journey_id": "service-run-1",
                    "journey": "change-driving-licence-address",
                    "status": "completed",
                    "result": {"new_address": {"postcode": "BS1 3AB"}},
                },
            },
            "duration_ms": 1,
        },
        {
            "run_id": "run-1",
            "sequence": 5,
            "timestamp": "2026-08-01T18:00:00.000Z",
            "type": "run_finished",
            "terminal_status": "completed",
        },
    ]

    common = convert_raw_trace(raw_events, source_trace="complete.jsonl")
    events = cast(list[JsonObject], common["events"])

    assert common["run"] == {
        "id": "run-1",
        "journey_id": "change-driving-licence-address",
        "implementation": "http_frontend",
        "status": "completed",
    }
    assert events[-1] == {
        "type": "journey_finished",
        "status": "completed",
        "result": {"new_address": {"postcode": "BS1 3AB"}},
    }
    assert sum(event["type"] == "journey_finished" for event in events) == 1


def test_batch_conversion_includes_abandoned_runs_and_ignores_resource_forks(
    tmp_path: Path,
) -> None:
    """Directory conversion does not fail when a journey stopped part-way through."""
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    raw_path = raw_directory / "trace.jsonl"
    raw_path.write_text(json.dumps(run_started()) + "\n", encoding="utf-8")
    (raw_directory / "._trace.jsonl").write_text("not json", encoding="utf-8")
    output_directory = tmp_path / "common"

    converted, incomplete = convert_paths(
        [raw_directory],
        output_directory=output_directory,
        output_format="json",
        overwrite=False,
    )

    assert (converted, incomplete) == (1, 1)
    output = json.loads(
        (output_directory / "trace.common.json").read_text(encoding="utf-8")
    )
    assert output["run"]["status"] == "incomplete"


def test_yaml_output_is_sparse_and_deterministic() -> None:
    """The dependency-free YAML writer preserves common trace ordering."""
    output = dump_yaml(
        {
            "schema_version": "0.1",
            "events": [
                {
                    "type": "values_proposed",
                    "values": {"confirmed": True, "line_2": None},
                }
            ],
        }
    )

    assert output == (
        'schema_version: "0.1"\n'
        "events:\n"
        '  - type: "values_proposed"\n'
        "    values:\n"
        "      confirmed: true\n"
        "      line_2: null\n"
    )
