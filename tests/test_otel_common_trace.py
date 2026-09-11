"""Tests for durable OTEL to common-trace conversion."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest
import yaml

from evaluation.otel_common_trace import convert_trace, decode_received_value


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def write_inputs(
    tmp_path: Path,
    *,
    process_id: str = "section2_about_baby",
    state_id: str = "prompt_is_baby_born",
) -> tuple[Path, Path, Path]:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "id": "ma-test",
                "journey_id": "dwp.maternity_allowance_ma1_claim",
                "input": {
                    "conversation_fixture": {"id": "ma-fixture", "version": "1"},
                    "checkpoint": {
                        "id": "captured-checkpoint",
                        "process_id": process_id,
                        "state_id": state_id,
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture_path = fixture_dir / "ma_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "id": "ma-fixture",
                "version": "1",
                "journey_id": "dwp.maternity_allowance_ma1_claim",
                "conversation": [{"role": "user", "content": "test"}],
            }
        ),
        encoding="utf-8",
    )
    return scenario_path, fixture_dir, fixture_path


def input_span(
    *,
    workflow_id: str,
    process_id: str = "section2_about_baby",
    state_id: str = "prompt_is_baby_born",
    assign_target: str = "is_baby_born",
    value_type: str = "bool",
    value: str = "False",
    start_time: int = 100,
) -> dict[str, object]:
    return {
        "name": "interpreter.InputState",
        "trace_id": "6cc99ce21539ab3657e2c6a366e6161b",
        "span_id": "62d9df6a6b8b6892",
        "start_time": start_time,
        "end_time": start_time + 1,
        "attributes": {
            "temporalWorkflowID": workflow_id,
            "state_id": state_id,
            "process_id": process_id,
            "schema_kind": "boolean" if value_type == "bool" else "string",
            "assign_target": assign_target,
            "outcome": "received",
            "received_value_type": value_type,
            "received_value": value,
        },
        "status": "UNSET",
    }


def test_baby_not_born_span_becomes_common_semantic_events(tmp_path: Path) -> None:
    scenario_path, fixture_dir, fixture_path = write_inputs(tmp_path)
    trace_path = tmp_path / "durable-otel.jsonl"
    workflow_id = "eval-ma-baby-not-born-a6f89cb5"
    write_jsonl(
        trace_path,
        [
            input_span(workflow_id="some-other-workflow"),
            input_span(workflow_id=workflow_id),
            input_span(
                workflow_id=workflow_id,
                state_id="prompt_due_date_unborn",
                assign_target="due_date",
                value_type="str",
                value="01/11/2026",
                start_time=200,
            ),
        ],
    )

    result = convert_trace(
        trace_path=trace_path,
        scenario_path=scenario_path,
        workflow_id=workflow_id,
        fixture_dir=fixture_dir,
    )

    assert result == {
        "schema_version": "0.1",
        "source_trace": "durable-otel.jsonl",
        "run": {
            "id": workflow_id,
            "journey_id": "dwp.maternity_allowance_ma1_claim",
            "implementation": "durable_poc",
            "status": "in_progress",
        },
        "initial_context": {
            "conversation_fixture": {
                "id": "ma-fixture",
                "version": "1",
                "sha256": sha256(fixture_path.read_bytes()).hexdigest(),
            }
        },
        "events": [
            {
                "type": "interaction_available",
                "interaction_id": "prompt_is_baby_born",
            },
            {
                "type": "values_submitted",
                "interaction_id": "prompt_is_baby_born",
                "values": {"is_baby_born": False},
            },
        ],
    }


def test_converter_preserves_natural_language_date_as_string(tmp_path: Path) -> None:
    scenario_path, fixture_dir, _ = write_inputs(
        tmp_path,
        process_id="section4_about_payment",
        state_id="prompt_date_stopped_work",
    )
    trace_path = tmp_path / "durable-otel.jsonl"
    workflow_id = "eval-ma-date-stopped-work-12345678"
    write_jsonl(
        trace_path,
        [
            input_span(
                workflow_id=workflow_id,
                process_id="section4_about_payment",
                state_id="prompt_date_stopped_work",
                assign_target="date_stopped_work",
                value_type="str",
                value="03/09/2026",
            )
        ],
    )

    result = convert_trace(
        trace_path=trace_path,
        scenario_path=scenario_path,
        workflow_id=workflow_id,
        fixture_dir=fixture_dir,
    )

    assert result["events"][1] == {
        "type": "values_submitted",
        "interaction_id": "prompt_date_stopped_work",
        "values": {"date_stopped_work": "03/09/2026"},
    }


def test_converter_requires_target_input_span(tmp_path: Path) -> None:
    scenario_path, fixture_dir, _ = write_inputs(tmp_path)
    trace_path = tmp_path / "durable-otel.jsonl"
    write_jsonl(trace_path, [input_span(workflow_id="different-workflow")])

    with pytest.raises(ValueError, match="No interpreter.InputState span found"):
        convert_trace(
            trace_path=trace_path,
            scenario_path=scenario_path,
            workflow_id="eval-ma-baby-not-born-missing",
            fixture_dir=fixture_dir,
        )


def test_decode_received_value_supports_structured_python_values() -> None:
    assert decode_received_value(
        {"received_value_type": "list", "received_value": "['employed', 'self_employed']"}
    ) == ["employed", "self_employed"]
    assert decode_received_value(
        {"received_value_type": "dict", "received_value": "{'answer': True}"}
    ) == {"answer": True}


def test_decode_received_value_rejects_invalid_boolean() -> None:
    with pytest.raises(ValueError, match="Cannot decode boolean"):
        decode_received_value(
            {
                "schema_kind": "boolean",
                "received_value_type": "bool",
                "received_value": "maybe",
            }
        )
