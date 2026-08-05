"""Convert raw journey JSONL traces into a small common trace format."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypeAlias, cast

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
ReadOnlyJsonObject: TypeAlias = Mapping[str, JsonValue]

COMMON_TRACE_VERSION = "0.1"
DEFAULT_OUTPUT_SUFFIX = ".common.yaml"
_SAFE_YAML_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class CommonTraceError(ValueError):
    """Raised when a raw trace cannot be converted safely."""


def convert_raw_trace(
    raw_events: Sequence[ReadOnlyJsonObject],
    *,
    source_trace: str,
) -> JsonObject:
    """Convert one ordered raw trace to the implementation-neutral format.

    The converter retains positive, externally meaningful events. It deliberately
    omits implementation mechanics such as agent invocation triggers, raw tool names,
    proposal-review flags and HTTP transport details. The source JSONL remains the
    authoritative record for those details.

    Args:
        raw_events: Parsed events from one raw JSONL trace.
        source_trace: Filename or other single reference to the raw trace.

    Returns:
        A common trace represented as JSON-compatible Python values.

    Raises:
        CommonTraceError: If the trace has no valid ``run_started`` event.
    """
    ordered_events = _ordered_events(raw_events)
    run_started = _first_event(ordered_events, "run_started")
    if run_started is None:
        msg = "Raw trace does not contain a valid run_started event"
        raise CommonTraceError(msg)

    run_id = _required_string(run_started, "run_id")
    journey_id = _required_string(run_started, "journey_id")
    implementation = _optional_string(run_started.get("consumer")) or "unknown"

    common_events: list[JsonValue] = []
    current_interaction_id: str | None = None
    invocation_interaction_id: str | None = None
    terminal_status: str | None = None
    terminal_emitted = False
    conversation_fixture: JsonObject | None = None

    for raw_event in ordered_events:
        event_type = _optional_string(raw_event.get("type"))

        if event_type == "fixture_loaded" and conversation_fixture is None:
            conversation_fixture = _convert_fixture_reference(raw_event)
            continue

        if event_type == "http_exchange":
            response_body = _http_response_body(raw_event)
            interaction_id = _interaction_id(response_body)
            if interaction_id is not None:
                current_interaction_id = interaction_id
                common_events.append(
                    {
                        "type": "interaction_available",
                        "interaction_id": interaction_id,
                    }
                )

            terminal = _terminal_response(response_body)
            if terminal is not None:
                terminal_status, terminal_result = terminal
                common_events.append(
                    _journey_finished_event(terminal_status, terminal_result)
                )
                terminal_emitted = True
            continue

        if event_type == "agent_invoked":
            invocation_interaction_id = _agent_interaction_id(raw_event)
            if invocation_interaction_id is not None:
                current_interaction_id = invocation_interaction_id
            continue

        if event_type == "agent_responded":
            interaction_id = invocation_interaction_id or current_interaction_id
            common_events.extend(
                _proposal_events(raw_event, interaction_id=interaction_id)
            )
            continue

        if event_type == "user_message":
            message = _optional_string(raw_event.get("message"))
            if message is not None:
                event: JsonObject = {
                    "type": "user_message",
                    "content": message,
                }
                _add_interaction_id(event, raw_event, current_interaction_id)
                common_events.append(event)
            continue

        if event_type == "agent_tool_completed":
            guidance_event = _guidance_event(
                raw_event,
                interaction_id=invocation_interaction_id or current_interaction_id,
            )
            if guidance_event is not None:
                common_events.append(guidance_event)
            continue

        if event_type == "answer_presented":
            event: JsonObject = {"type": "answer_presented"}
            _add_interaction_id(event, raw_event, current_interaction_id)
            common_events.append(event)
            continue

        if event_type == "result_submitted":
            result = _json_object(raw_event.get("result"))
            if result is not None:
                event: JsonObject = {
                    "type": "values_submitted",
                    "values": result,
                }
                _add_interaction_id(event, raw_event, current_interaction_id)
                common_events.append(event)
            continue

        if event_type == "agent_failed":
            event: JsonObject = {"type": "assistance_failed"}
            interaction_id = invocation_interaction_id or current_interaction_id
            if interaction_id is not None:
                event["interaction_id"] = interaction_id
            common_events.append(event)
            continue

        if event_type == "run_finished":
            terminal_status = (
                _optional_string(raw_event.get("terminal_status")) or "finished"
            )
            if not terminal_emitted:
                common_events.append(_journey_finished_event(terminal_status, None))
                terminal_emitted = True

    run_status = terminal_status or "incomplete"
    common_trace: JsonObject = {
        "schema_version": COMMON_TRACE_VERSION,
        "source_trace": source_trace,
        "run": {
            "id": run_id,
            "journey_id": journey_id,
            "implementation": implementation,
            "status": run_status,
        },
    }
    if conversation_fixture is not None:
        common_trace["initial_context"] = {
            "conversation_fixture": conversation_fixture,
        }
    common_trace["events"] = common_events
    return common_trace


def load_raw_trace(path: Path) -> list[JsonObject]:
    """Load a JSONL raw trace from disk.

    Args:
        path: Raw trace path.

    Returns:
        Parsed JSON objects in file order.

    Raises:
        CommonTraceError: If a line is invalid JSON or is not a JSON object.
    """
    events: list[JsonObject] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        msg = f"Could not read {path}: {error}"
        raise CommonTraceError(msg) from error

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as error:
            msg = f"{path}:{line_number}: invalid JSON: {error.msg}"
            raise CommonTraceError(msg) from error
        if not isinstance(parsed, dict):
            msg = f"{path}:{line_number}: trace event must be a JSON object"
            raise CommonTraceError(msg)
        events.append(cast(JsonObject, parsed))
    return events


def write_common_trace(
    trace: ReadOnlyJsonObject,
    path: Path,
    *,
    output_format: str,
) -> None:
    """Write a common trace as YAML or JSON.

    Args:
        trace: Common trace to serialise.
        path: Destination file.
        output_format: Either ``yaml`` or ``json``.

    Raises:
        CommonTraceError: If the requested format is unsupported or writing fails.
    """
    if output_format == "yaml":
        content = dump_yaml(trace)
    elif output_format == "json":
        content = json.dumps(trace, indent=2, ensure_ascii=False) + "\n"
    else:
        msg = f"Unsupported output format: {output_format}"
        raise CommonTraceError(msg)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as error:
        msg = f"Could not write {path}: {error}"
        raise CommonTraceError(msg) from error


def dump_yaml(value: ReadOnlyJsonObject) -> str:
    """Serialise JSON-compatible values as deterministic YAML 1.2.

    Strings are JSON-quoted, which is valid YAML 1.2 and avoids ambiguous implicit
    types. This keeps the converter dependency-free while producing readable output.

    Args:
        value: Top-level mapping to serialise.

    Returns:
        YAML text ending in a newline.
    """
    lines = _yaml_lines(cast(JsonValue, dict(value)), indent=0)
    return "\n".join(lines) + "\n"


def convert_paths(
    inputs: Sequence[Path],
    *,
    output_directory: Path,
    output_format: str,
    overwrite: bool,
) -> tuple[int, int]:
    """Convert raw trace files discovered from file or directory inputs.

    Args:
        inputs: Files or directories containing ``.jsonl`` traces.
        output_directory: Directory for generated common traces.
        output_format: Either ``yaml`` or ``json``.
        overwrite: Whether existing outputs may be replaced.

    Returns:
        A tuple of converted and incomplete-run counts.

    Raises:
        CommonTraceError: If no input traces are found or an output already exists.
    """
    paths = discover_raw_traces(inputs)
    if not paths:
        msg = "No .jsonl raw traces were found"
        raise CommonTraceError(msg)

    converted = 0
    incomplete = 0
    suffix = ".common.json" if output_format == "json" else DEFAULT_OUTPUT_SUFFIX
    for raw_path in paths:
        output_path = output_directory / f"{raw_path.stem}{suffix}"
        if output_path.exists() and not overwrite:
            msg = (
                f"Output already exists: {output_path}; "
                "pass --overwrite to replace it"
            )
            raise CommonTraceError(msg)
        raw_events = load_raw_trace(raw_path)
        common_trace = convert_raw_trace(raw_events, source_trace=raw_path.name)
        run = _json_object(common_trace.get("run"))
        if run is not None and run.get("status") == "incomplete":
            incomplete += 1
        write_common_trace(common_trace, output_path, output_format=output_format)
        converted += 1
    return converted, incomplete


def discover_raw_traces(inputs: Sequence[Path]) -> list[Path]:
    """Return unique raw JSONL trace files from file and directory inputs.

    Args:
        inputs: Trace files or directories to search recursively.

    Returns:
        Sorted unique paths. macOS resource-fork files are ignored.
    """
    discovered: set[Path] = set()
    for input_path in inputs:
        if input_path.is_file() and input_path.suffix == ".jsonl":
            if not input_path.name.startswith("._"):
                discovered.add(input_path)
            continue
        if input_path.is_dir():
            discovered.update(
                path
                for path in input_path.rglob("*.jsonl")
                if path.is_file() and not path.name.startswith("._")
            )
    return sorted(discovered)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the common-trace converter command-line interface.

    Args:
        argv: Optional command-line arguments excluding the program name.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(
        description="Convert raw journey JSONL traces to common traces.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Raw .jsonl file or directory containing raw traces.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".common-traces"),
        help="Output directory (default: .common-traces).",
    )
    parser.add_argument(
        "--format",
        choices=("yaml", "json"),
        default="yaml",
        dest="output_format",
        help="Output format (default: yaml).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing common trace files.",
    )
    args = parser.parse_args(argv)

    try:
        converted, incomplete = convert_paths(
            args.inputs,
            output_directory=args.output_dir,
            output_format=args.output_format,
            overwrite=args.overwrite,
        )
    except CommonTraceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"Converted {converted} raw trace(s) to {args.output_dir} "
        f"({incomplete} incomplete)."
    )
    return 0


def _ordered_events(
    raw_events: Sequence[ReadOnlyJsonObject],
) -> list[ReadOnlyJsonObject]:
    indexed = list(enumerate(raw_events))

    def key(item: tuple[int, ReadOnlyJsonObject]) -> tuple[int, int]:
        index, event = item
        sequence = event.get("sequence")
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            return sequence, index
        return index, index

    return [event for _, event in sorted(indexed, key=key)]


def _first_event(
    raw_events: Iterable[ReadOnlyJsonObject],
    event_type: str,
) -> ReadOnlyJsonObject | None:
    return next(
        (
            event
            for event in raw_events
            if _optional_string(event.get("type")) == event_type
        ),
        None,
    )


def _convert_fixture_reference(
    event: ReadOnlyJsonObject,
) -> JsonObject | None:
    """Return fixture identity without duplicating its conversation content."""
    converted: JsonObject = {}
    for source_key, target_key in (
        ("fixture_id", "id"),
        ("fixture_version", "version"),
        ("fixture_sha256", "sha256"),
    ):
        value = _optional_string(event.get(source_key))
        if value is not None:
            converted[target_key] = value
    return converted or None


def _http_response_body(event: ReadOnlyJsonObject) -> ReadOnlyJsonObject | None:
    response = _json_object(event.get("response"))
    if response is None:
        return None
    return _json_object(response.get("body"))


def _interaction_id(response_body: ReadOnlyJsonObject | None) -> str | None:
    if response_body is None:
        return None
    interaction = _json_object(response_body.get("interaction"))
    if interaction is None:
        return None
    return _optional_string(interaction.get("id"))


def _terminal_response(
    response_body: ReadOnlyJsonObject | None,
) -> tuple[str, JsonObject | None] | None:
    if response_body is None or "next_action" in response_body:
        return None
    status = _optional_string(response_body.get("status"))
    identifies_journey = "journey" in response_body or "journey_id" in response_body
    if status is None or not identifies_journey:
        return None
    return status, _json_object(response_body.get("result"))


def _journey_finished_event(
    status: str,
    result: ReadOnlyJsonObject | None,
) -> JsonObject:
    event: JsonObject = {
        "type": "journey_finished",
        "status": status,
    }
    if result is not None:
        event["result"] = dict(result)
    return event


def _agent_interaction_id(event: ReadOnlyJsonObject) -> str | None:
    agent_input = _json_object(event.get("input"))
    if agent_input is None:
        return None
    interaction = _json_object(agent_input.get("interaction"))
    if interaction is None:
        return None
    return _optional_string(interaction.get("id"))


def _proposal_events(
    event: ReadOnlyJsonObject,
    *,
    interaction_id: str | None,
) -> list[JsonValue]:
    actions_value = event.get("actions")
    if isinstance(actions_value, list):
        actions = actions_value
    else:
        singular_action = event.get("action")
        actions = [singular_action] if isinstance(singular_action, dict) else []

    converted: list[JsonValue] = []
    for action_value in actions:
        action = _json_object(action_value)
        if action is None or action.get("type") != "propose_values":
            continue
        values = _json_object(action.get("values"))
        if values is None:
            continue
        proposal: JsonObject = {
            "type": "values_proposed",
        }
        if interaction_id is not None:
            proposal["interaction_id"] = interaction_id
        proposal["values"] = dict(values)
        converted.append(proposal)
    return converted


def _guidance_event(
    event: ReadOnlyJsonObject,
    *,
    interaction_id: str | None,
) -> JsonObject | None:
    if event.get("tool") != "get_journey_guidance":
        return None
    result = _json_object(event.get("result"))
    if result is None:
        return None
    source_id = _optional_string(result.get("id"))
    if source_id is None:
        return None

    source: JsonObject = {"id": source_id}
    version = _optional_string(result.get("version"))
    if version is not None:
        source["version"] = version

    converted: JsonObject = {
        "type": "guidance_retrieved",
    }
    if interaction_id is not None:
        converted["interaction_id"] = interaction_id
    converted["source"] = source
    return converted


def _add_interaction_id(
    converted: JsonObject,
    raw_event: ReadOnlyJsonObject,
    fallback: str | None,
) -> None:
    interaction_id = _optional_string(raw_event.get("interaction_id")) or fallback
    if interaction_id is not None:
        converted["interaction_id"] = interaction_id


def _required_string(event: ReadOnlyJsonObject, key: str) -> str:
    value = _optional_string(event.get(key))
    if value is None:
        msg = f"run_started field {key!r} must be a non-empty string"
        raise CommonTraceError(msg)
    return value


def _optional_string(value: JsonValue | object) -> str | None:
    return value if isinstance(value, str) and value else None


def _json_object(value: JsonValue | object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    return cast(JsonObject, value)


def _copy_json_list(values: list[JsonValue]) -> list[JsonValue]:
    return cast(list[JsonValue], json.loads(json.dumps(values)))


def _yaml_lines(value: JsonValue, *, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]
        lines: list[str] = []
        for key, child in value.items():
            rendered_key = key if _SAFE_YAML_KEY.fullmatch(key) else _yaml_scalar(key)
            if isinstance(child, (dict, list)) and child:
                lines.append(f"{prefix}{rendered_key}:")
                lines.extend(_yaml_lines(child, indent=indent + 2))
            else:
                lines.append(
                    f"{prefix}{rendered_key}: {_yaml_inline_value(child)}"
                )
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for child in value:
            if isinstance(child, dict) and child:
                first_key, first_value = next(iter(child.items()))
                rendered_key = (
                    first_key
                    if _SAFE_YAML_KEY.fullmatch(first_key)
                    else _yaml_scalar(first_key)
                )
                if isinstance(first_value, (dict, list)) and first_value:
                    lines.append(f"{prefix}- {rendered_key}:")
                    lines.extend(_yaml_lines(first_value, indent=indent + 4))
                else:
                    lines.append(
                        f"{prefix}- {rendered_key}: {_yaml_inline_value(first_value)}"
                    )
                remaining = dict(list(child.items())[1:])
                if remaining:
                    lines.extend(_yaml_lines(remaining, indent=indent + 2))
            elif isinstance(child, list) and child:
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(child, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_inline_value(child)}")
        return lines

    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_inline_value(value: JsonValue) -> str:
    if isinstance(value, dict):
        return "{}" if not value else _yaml_scalar(value)
    if isinstance(value, list):
        return "[]" if not value else _yaml_scalar(value)
    return _yaml_scalar(value)


def _yaml_scalar(value: JsonValue | object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
