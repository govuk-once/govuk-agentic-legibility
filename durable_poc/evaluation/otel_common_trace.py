"""Convert durable SFSM OpenTelemetry JSONL into the common trace vocabulary."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml

from evaluation.scenario_case import load_document, load_scenario_case



def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read OpenTelemetry exporter JSONL, rejecting malformed records."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on {path}:{line_number}: {error.msg}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        records.append(value)
    return records


def _decode_typed_value(
    attributes: dict[str, Any], *, value_key: str, type_key: str, label: str
) -> Any:
    """Decode a typed value stored as string OTEL attributes."""
    raw = attributes.get(value_key)
    value_type = attributes.get(type_key)
    schema_kind = attributes.get("schema_kind")

    if not isinstance(raw, str):
        raise ValueError(f"{label} span is missing string attribute {value_key}")

    if value_type == "bool" or (value_type is None and schema_kind == "boolean"):
        normalised = raw.strip().lower()
        if normalised == "true":
            return True
        if normalised == "false":
            return False
        raise ValueError(f"Cannot decode boolean {value_key} {raw!r}")

    if value_type == "str":
        return raw
    if value_type == "int":
        try:
            return int(raw)
        except ValueError as error:
            raise ValueError(f"Cannot decode integer {value_key} {raw!r}") from error
    if value_type == "float":
        try:
            return float(raw)
        except ValueError as error:
            raise ValueError(f"Cannot decode float {value_key} {raw!r}") from error
    if value_type in {"NoneType", "none", "null"}:
        if raw.strip().lower() not in {"none", "null"}:
            raise ValueError(f"Cannot decode null {value_key} {raw!r}")
        return None
    if value_type in {"list", "dict"}:
        try:
            decoded = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as error:
            raise ValueError(
                f"Cannot decode {value_type} {value_key} {raw!r}"
            ) from error
        expected_type = list if value_type == "list" else dict
        if not isinstance(decoded, expected_type):
            raise ValueError(
                f"{type_key} is {value_type!r} but value decoded as "
                f"{type(decoded).__name__!r}"
            )
        return decoded

    raise ValueError(f"Unsupported {type_key} {value_type!r}")


def decode_received_value(attributes: dict[str, Any]) -> Any:
    """Decode the string-valued OTEL representation of an accepted input."""
    return _decode_typed_value(
        attributes,
        value_key="received_value",
        type_key="received_value_type",
        label="InputState",
    )


def decode_rejected_value(attributes: dict[str, Any]) -> Any:
    """Decode the exact value rejected by the executor update validator."""
    return _decode_typed_value(
        attributes,
        value_key="rejected_value",
        type_key="rejected_value_type",
        label="input_validation.rejected",
    )


def _target_spans(
    records: list[dict[str, Any]],
    *,
    workflow_id: str,
    process_id: str,
    state_id: str,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for record in records:
        if record.get("name") != "interpreter.InputState":
            continue
        attributes = record.get("attributes")
        if not isinstance(attributes, dict):
            continue
        if attributes.get("temporalWorkflowID") != workflow_id:
            continue
        if attributes.get("process_id") != process_id:
            continue
        if attributes.get("state_id") != state_id:
            continue
        spans.append(record)

    spans.sort(key=lambda span: span.get("start_time", 0))
    return spans



def _target_rejection_spans(
    records: list[dict[str, Any]],
    *,
    workflow_id: str,
    process_id: str,
    state_id: str,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for record in records:
        if record.get("name") != "interpreter.input_validation.rejected":
            continue
        attributes = record.get("attributes")
        if not isinstance(attributes, dict):
            continue
        if attributes.get("temporalWorkflowID") != workflow_id:
            continue
        if attributes.get("process_id") != process_id:
            continue
        if attributes.get("state_id") != state_id:
            continue
        spans.append(record)

    spans.sort(key=lambda span: span.get("end_time", span.get("start_time", 0)))
    return spans

def convert_trace(
    *,
    trace_path: Path,
    scenario_path: Path,
    workflow_id: str,
) -> dict[str, Any]:
    """Convert one targeted durable evaluation run into a common trace object."""
    scenario_case = load_scenario_case(scenario_path)
    scenario = scenario_case.scenario
    fixture = scenario_case.conversation
    fixture_path = scenario_case.conversation_path
    process_id, state_id = scenario_case.target

    fixture_id = fixture["id"]
    fixture_version = fixture["version"]
    journey_id = scenario["journey_id"]

    records = read_jsonl(trace_path)
    spans = _target_spans(
        records,
        workflow_id=workflow_id,
        process_id=process_id,
        state_id=state_id,
    )
    rejection_spans = _target_rejection_spans(
        records,
        workflow_id=workflow_id,
        process_id=process_id,
        state_id=state_id,
    )
    if not spans and not rejection_spans:
        raise ValueError(
            "No accepted or rejected input span found for "
            f"workflow {workflow_id!r} at {process_id}.{state_id}"
        )

    events: list[dict[str, Any]] = [
        {
            "type": "interaction_available",
            "interaction_id": state_id,
        }
    ]

    semantic_events: list[tuple[int, dict[str, Any]]] = []
    for span in rejection_spans:
        attributes = span["attributes"]
        assign_target = attributes.get("assign_target")
        if not isinstance(assign_target, str) or not assign_target:
            raise ValueError("Rejected-input span is missing assign_target")

        rejection_code = attributes.get("rejection_code")
        rejection_message = attributes.get("rejection_message")
        event: dict[str, Any] = {
            "type": "values_rejected",
            "interaction_id": state_id,
            "values": {
                assign_target: decode_rejected_value(attributes),
            },
        }
        if isinstance(rejection_code, str) and rejection_code:
            event["reason"] = rejection_code
        if isinstance(rejection_message, str) and rejection_message:
            event["message"] = rejection_message
        semantic_events.append(
            (span.get("end_time", span.get("start_time", 0)), event)
        )

    for span in spans:
        attributes = span["attributes"]
        if attributes.get("outcome") != "received":
            continue

        assign_target = attributes.get("assign_target")
        if not isinstance(assign_target, str) or not assign_target:
            raise ValueError("Received InputState span is missing assign_target")
        semantic_events.append(
            (
                span.get("end_time", span.get("start_time", 0)),
                {
                    "type": "values_submitted",
                    "interaction_id": state_id,
                    "values": {
                        assign_target: decode_received_value(attributes),
                    },
                },
            )
        )

    semantic_events.sort(key=lambda item: item[0])
    events.extend(event for _, event in semantic_events)

    fixture_hash = sha256(fixture_path.read_bytes()).hexdigest()
    return {
        "schema_version": "0.1",
        "source_trace": trace_path.name,
        "run": {
            "id": workflow_id,
            "journey_id": journey_id,
            "implementation": "durable_poc",
            # Targeted eval workflows are intentionally terminated after the
            # interaction under test; they do not complete the service journey.
            "status": "in_progress",
        },
        "initial_context": {
            "conversation_fixture": {
                "id": fixture_id,
                "version": fixture_version,
                "sha256": fixture_hash,
            }
        },
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert durable SFSM OTEL JSONL to common trace YAML."
    )
    parser.add_argument("trace", type=Path, help="Raw OTEL JSONL file")
    parser.add_argument(
        "scenario",
        type=Path,
        help=(
            "Scenario case directory or path relative to evaluation/scenarios"
        ),
    )
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    common_trace = convert_trace(
        trace_path=args.trace,
        scenario_path=args.scenario,
        workflow_id=args.workflow_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(common_trace, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote common trace to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
