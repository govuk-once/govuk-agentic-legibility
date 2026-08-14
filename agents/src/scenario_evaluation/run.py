"""Run evaluation scenarios end to end against the current journey application."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 - fixed local common-trace CLI invocation
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import requests

from agents.src.scenario_evaluation.evaluator import (
    EvaluationInputError,
    EvaluationResult,
    evaluate_common_trace,
    load_document,
)

JsonObject = dict[str, Any]
ReadOnlyJsonObject = Mapping[str, Any]
TraceConverter = Callable[[Path, Path], Path]

DEFAULT_API_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_OUTPUT_DIR = Path(".traces") / "evaluation-runs"
MAX_INTERACTIONS = 20


class ScenarioExecutionError(RuntimeError):
    """Raised when the current prototype cannot execute a scenario."""


class JourneyApplicationProtocol(Protocol):
    """Operations the current prototype runner needs from a journey application."""

    def start(self, journey_id: str, fixture_id: str) -> JsonObject:
        """Start a journey run."""

    def submit(self, run_id: str, result: ReadOnlyJsonObject) -> JsonObject:
        """Submit one reviewed interaction result."""

    def trace(self, run_id: str) -> list[JsonObject]:
        """Return the raw trace for a run."""


@dataclass(frozen=True)
class ScenarioRunResult:
    """Artifacts and evaluation result for one scenario run."""

    scenario_id: str
    run_id: str | None
    raw_trace_path: Path | None
    common_trace_path: Path | None
    evaluation: EvaluationResult | None
    execution_error: str | None

    @property
    def passed(self) -> bool:
        """Return whether both execution and semantic evaluation passed."""
        return (
            self.execution_error is None
            and self.evaluation is not None
            and self.evaluation.passed
        )


class JourneyApplicationClient:
    """HTTP adapter for the current journey application."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        """Create a client for a running journey application."""
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()

    def start(self, journey_id: str, fixture_id: str) -> JsonObject:
        """Start an assisted journey using a conversation fixture."""
        return self._request(
            "POST",
            "/api/journey-runs",
            {"journey_id": journey_id, "fixture_id": fixture_id},
        )

    def submit(self, run_id: str, result: ReadOnlyJsonObject) -> JsonObject:
        """Submit one result for the active interaction."""
        return self._request(
            "POST",
            f"/api/journey-runs/{run_id}/results",
            {"result": dict(result)},
        )

    def trace(self, run_id: str) -> list[JsonObject]:
        """Fetch raw trace events for a run."""
        events = self._request("GET", f"/api/journey-runs/{run_id}/trace").get(
            "events"
        )
        if not isinstance(events, list) or not all(
            isinstance(event, Mapping) for event in events
        ):
            raise ScenarioExecutionError("Trace response must contain an events list")
        return [dict(event) for event in events]

    def _request(
        self,
        method: str,
        path: str,
        body: ReadOnlyJsonObject | None = None,
    ) -> JsonObject:
        try:
            response = self._session.request(
                method,
                f"{self._base_url}{path}",
                json=dict(body) if body is not None else None,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise ScenarioExecutionError(
                f"Could not call journey application {method} {path}: {error}"
            ) from error
        if not isinstance(payload, Mapping):
            raise ScenarioExecutionError(f"{method} {path} must return a JSON object")
        return dict(payload)


def run_scenario_file(
    scenario_path: Path,
    client: JourneyApplicationProtocol,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    converter: TraceConverter | None = None,
) -> ScenarioRunResult:
    """Run one scenario, convert its raw trace and evaluate the common trace."""
    scenario = load_document(scenario_path)
    scenario_id = _required_string(scenario, "id", "scenario")
    journey_id = _required_string(scenario, "journey_id", "scenario")
    scenario_input = _required_mapping(scenario, "input", "scenario")
    fixture = _required_mapping(
        scenario_input,
        "conversation_fixture",
        "scenario.input",
    )
    fixture_id = _required_string(
        fixture,
        "id",
        "scenario.input.conversation_fixture",
    )

    try:
        run = client.start(journey_id, fixture_id)
        run_id = _run_id(run)
    except ScenarioExecutionError as error:
        return ScenarioRunResult(scenario_id, None, None, None, None, str(error))

    execution_error = _drive_run(client, run_id, run)
    try:
        events = client.trace(run_id)
    except ScenarioExecutionError as error:
        return ScenarioRunResult(
            scenario_id,
            run_id,
            None,
            None,
            None,
            _combine_errors(execution_error, str(error)),
        )

    run_dir = output_dir / scenario_id / run_id
    raw_path = run_dir / "raw.jsonl"
    _write_jsonl(raw_path, events)

    try:
        common_path = (converter or _convert_raw_trace)(raw_path, run_dir / "common")
        evaluation = evaluate_common_trace(scenario, load_document(common_path))
    except (ScenarioExecutionError, EvaluationInputError) as error:
        return ScenarioRunResult(
            scenario_id,
            run_id,
            raw_path,
            None,
            None,
            _combine_errors(execution_error, str(error)),
        )

    return ScenarioRunResult(
        scenario_id,
        run_id,
        raw_path,
        common_path,
        evaluation,
        execution_error,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one scenario, or all scenario YAML files in a directory."""
    parser = argparse.ArgumentParser(
        description=(
            "Run scenarios through the current journey application, convert raw "
            "traces and evaluate the resulting common traces."
        )
    )
    parser.add_argument("scenarios", type=Path, help="Scenario YAML file or directory")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    try:
        paths = _scenario_paths(args.scenarios)
    except ScenarioExecutionError as error:
        print(f"ERROR: {error}")
        return 2

    client = JourneyApplicationClient(args.api_base_url)
    results: list[ScenarioRunResult] = []
    for path in paths:
        try:
            result = run_scenario_file(path, client, args.output_dir)
        except EvaluationInputError as error:
            print(f"ERROR {path}: {error}")
            return 2
        results.append(result)
        _print_result(result)

    passed = sum(result.passed for result in results)
    failed = len(results) - passed
    noun = "scenario" if len(results) == 1 else "scenarios"
    print(f"\n{len(results)} {noun}: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def _drive_run(
    client: JourneyApplicationProtocol,
    run_id: str,
    initial_run: ReadOnlyJsonObject,
) -> str | None:
    run = dict(initial_run)
    for _ in range(MAX_INTERACTIONS):
        if _is_terminal(run):
            return None

        interaction_id = _interaction_id(run)
        try:
            result = _automatic_user_result(run)
            if result is None:
                result, error = _latest_proposed_values(
                    client.trace(run_id), interaction_id
                )
            else:
                error = None
        except ScenarioExecutionError as error:
            return str(error)
        if error is not None:
            return error
        if result is None:
            return (
                "No propose_values action was available for interaction "
                f"{interaction_id!r}; the automated run cannot continue"
            )

        try:
            run = client.submit(run_id, result)
        except ScenarioExecutionError as error:
            return f"Could not submit interaction {interaction_id!r}: {error}"

    return f"Run exceeded the {MAX_INTERACTIONS}-interaction safety limit"


def _automatic_user_result(run: ReadOnlyJsonObject) -> JsonObject | None:
    """Return a deterministic user response for service-owned confirmation.

    Ordinary form values are always taken from the agent's ``propose_values``
    output and accepted unchanged by the harness. A service confirmation is
    different: the harness itself acts as the user, using the advertised
    confirmation schema rather than asking the model to make that decision.
    """
    if run.get("status") != "ready_for_confirmation":
        return None

    interaction = run.get("interaction")
    if not isinstance(interaction, Mapping):
        raise ScenarioExecutionError(
            "Confirmation response must contain an interaction object"
        )
    schema = interaction.get("input_schema")
    if not isinstance(schema, Mapping):
        raise ScenarioExecutionError(
            "Confirmation interaction must contain an input_schema object"
        )
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        raise ScenarioExecutionError(
            "Confirmation input_schema must advertise properties and required fields"
        )

    required_fields = [field for field in required if isinstance(field, str)]
    if len(required_fields) != 1:
        raise ScenarioExecutionError(
            "Automated confirmation requires exactly one required field"
        )

    field = required_fields[0]
    definition = properties.get(field)
    if not isinstance(definition, Mapping) or definition.get("type") != "boolean":
        raise ScenarioExecutionError(
            "Automated confirmation requires one required boolean field"
        )
    return {field: True}


def _latest_proposed_values(
    events: Sequence[ReadOnlyJsonObject],
    interaction_id: str,
) -> tuple[JsonObject | None, str | None]:
    latest: JsonObject | None = None
    awaiting_response = False

    for event in events:
        event_type = event.get("type")
        if event_type == "agent_invoked":
            awaiting_response = _invocation_interaction_id(event) == interaction_id
        elif awaiting_response and event_type == "agent_failed":
            latest = None
            awaiting_response = False
        elif awaiting_response and event_type == "agent_responded":
            proposals = _proposal_actions(event)
            if len(proposals) > 1:
                return None, (
                    f"Agent returned {len(proposals)} propose_values actions for "
                    f"interaction {interaction_id!r}"
                )
            latest = proposals[0] if proposals else None
            awaiting_response = False

    return latest, None


def _proposal_actions(event: ReadOnlyJsonObject) -> list[JsonObject]:
    actions = event.get("actions")
    if not isinstance(actions, list):
        old_action = event.get("action")
        actions = [old_action] if isinstance(old_action, Mapping) else []

    proposals: list[JsonObject] = []
    for action in actions:
        if not isinstance(action, Mapping) or action.get("type") != "propose_values":
            continue
        values = action.get("values")
        if isinstance(values, Mapping):
            proposals.append(dict(values))
    return proposals


def _invocation_interaction_id(event: ReadOnlyJsonObject) -> str | None:
    raw_input = event.get("input")
    if not isinstance(raw_input, Mapping):
        return None
    interaction = raw_input.get("interaction")
    if not isinstance(interaction, Mapping):
        return None
    value = interaction.get("id")
    return value if isinstance(value, str) else None


def _convert_raw_trace(raw_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # nosec B603 - fixed Python module invocation
        [
            sys.executable,
            "-m",
            "agents.src.common_trace",
            str(raw_path),
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ScenarioExecutionError(f"Common-trace conversion failed: {detail}")

    candidates = sorted(
        [
            *output_dir.rglob("*.yaml"),
            *output_dir.rglob("*.yml"),
            *output_dir.rglob("*.json"),
        ]
    )
    if len(candidates) != 1:
        raise ScenarioExecutionError(
            "Common-trace conversion must produce exactly one YAML or JSON file"
        )
    return candidates[0]


def _write_jsonl(path: Path, events: Sequence[ReadOnlyJsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{json.dumps(dict(event), separators=(',', ':'))}\n" for event in events
    ]
    path.write_text("".join(lines), encoding="utf-8")


def _scenario_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ScenarioExecutionError(f"Scenario path does not exist: {path}")
    paths = sorted([*path.glob("*.yaml"), *path.glob("*.yml")])
    if not paths:
        raise ScenarioExecutionError(f"No scenario YAML files found in {path}")
    return paths


def _run_id(run: ReadOnlyJsonObject) -> str:
    value = run.get("run_id")
    if not isinstance(value, str) or not value:
        raise ScenarioExecutionError("Journey response must contain a non-empty run_id")
    return value


def _interaction_id(run: ReadOnlyJsonObject) -> str:
    interaction = run.get("interaction")
    if not isinstance(interaction, Mapping):
        raise ScenarioExecutionError(
            "Non-terminal journey run must contain an interaction object"
        )
    value = interaction.get("id")
    if not isinstance(value, str) or not value:
        raise ScenarioExecutionError("Journey interaction must contain a non-empty id")
    return value


def _is_terminal(run: ReadOnlyJsonObject) -> bool:
    terminal = run.get("terminal")
    return terminal if isinstance(terminal, bool) else run.get("interaction") is None


def _required_mapping(
    value: ReadOnlyJsonObject,
    key: str,
    context: str,
) -> ReadOnlyJsonObject:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise EvaluationInputError(f"{context}.{key} must be an object")
    return item


def _required_string(value: ReadOnlyJsonObject, key: str, context: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise EvaluationInputError(f"{context}.{key} must be a non-empty string")
    return item


def _combine_errors(first: str | None, second: str) -> str:
    return second if first is None else f"{first}; {second}"


def _print_result(result: ScenarioRunResult) -> None:
    print(f"{'PASS' if result.passed else 'FAIL'} {result.scenario_id}")
    if result.execution_error is not None:
        print(f"  - execution: {result.execution_error}")
    if result.evaluation is not None:
        for issue in result.evaluation.issues:
            print(f"  - {issue.path}: {issue.message}")
    if result.raw_trace_path is not None:
        print(f"  raw trace: {result.raw_trace_path}")
    if result.common_trace_path is not None:
        print(f"  common trace: {result.common_trace_path}")


if __name__ == "__main__":
    raise SystemExit(main())
