"""Deterministic evaluation of common traces against scenario expectations."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

JsonObject = dict[str, Any]
ReadOnlyJsonObject = Mapping[str, Any]

SUPPORTED_SCENARIO_VERSION = "0.1"
SUPPORTED_COMMON_TRACE_VERSION = "0.1"


@dataclass(frozen=True)
class EvaluationIssue:
    """One failed expectation."""

    path: str
    message: str


@dataclass(frozen=True)
class EvaluationResult:
    """Outcome of evaluating one common trace against one scenario."""

    scenario_id: str
    passed: bool
    issues: tuple[EvaluationIssue, ...]


@dataclass(frozen=True)
class BranchDefinition:
    """Observable service interactions that identify one semantic branch."""

    required_interactions: frozenset[str]
    forbidden_interactions: frozenset[str]


@dataclass(frozen=True)
class EquivalenceRule:
    """One permitted relaxation from exact semantic equality."""

    rule_type: str
    target: str
    paths: tuple[str, ...]


_BRANCHES: dict[str, dict[str, BranchDefinition]] = {
    "change-driving-licence-address": {
        "manual_entry": BranchDefinition(
            required_interactions=frozenset({"enter_address_manually"}),
            forbidden_interactions=frozenset({"find_address_by_postcode"}),
        ),
        "postcode_lookup": BranchDefinition(
            required_interactions=frozenset({"find_address_by_postcode"}),
            forbidden_interactions=frozenset({"enter_address_manually"}),
        ),
    }
}


class EvaluationInputError(ValueError):
    """Raised when a scenario or common trace cannot be evaluated."""


def load_document(path: Path) -> JsonObject:
    """Load a YAML or JSON document as a mapping.

    Args:
        path: YAML or JSON file to load.

    Returns:
        Parsed top-level mapping.

    Raises:
        EvaluationInputError: If the document cannot be parsed as an object.
    """
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            value = json.loads(text)
        else:
            value = yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise EvaluationInputError(f"Could not load {path}: {error}") from error

    if not isinstance(value, Mapping):
        raise EvaluationInputError(f"{path} must contain a top-level object")
    return dict(value)


def evaluate_common_trace(
    scenario: ReadOnlyJsonObject,
    trace: ReadOnlyJsonObject,
) -> EvaluationResult:
    """Compare one common trace with one scenario's semantic expectations.

    Scenario expectations are opt-in. Omitting an evaluation dimension means the
    evaluator does not score that dimension. When ``expected.assistance`` is present,
    however, it is exhaustive: undeclared assistance is treated as unexpected output.

    Args:
        scenario: Parsed evaluation scenario.
        trace: Parsed common trace.

    Returns:
        Pass/fail result with deterministic mismatch reasons.

    Raises:
        EvaluationInputError: If either document uses an unsupported or malformed
            structure required by the evaluator.
    """
    _require_version(scenario, SUPPORTED_SCENARIO_VERSION, "scenario")
    _require_version(trace, SUPPORTED_COMMON_TRACE_VERSION, "common trace")

    scenario_id = _required_string(scenario, "id", "scenario")
    journey_id = _required_string(scenario, "journey_id", "scenario")
    expected = _required_mapping(scenario, "expected", "scenario")
    equivalence_rules = _equivalence_rules(scenario)

    issues: list[EvaluationIssue] = []
    _evaluate_identity(scenario, trace, journey_id, issues)

    if "assistance" in expected:
        _evaluate_assistance(expected, trace, equivalence_rules, issues)
        _evaluate_failures(trace, issues)

    if "journey" in expected:
        _evaluate_journey(
            expected,
            trace,
            journey_id,
            equivalence_rules,
            issues,
        )

    return EvaluationResult(
        scenario_id=scenario_id,
        passed=not issues,
        issues=tuple(issues),
    )


def _evaluate_identity(
    scenario: ReadOnlyJsonObject,
    trace: ReadOnlyJsonObject,
    journey_id: str,
    issues: list[EvaluationIssue],
) -> None:
    run = _required_mapping(trace, "run", "common trace")
    actual_journey_id = _required_string(run, "journey_id", "common trace.run")
    if actual_journey_id != journey_id:
        issues.append(
            EvaluationIssue(
                "journey_id",
                f"expected {journey_id!r}, observed {actual_journey_id!r}",
            )
        )

    scenario_input = _required_mapping(scenario, "input", "scenario")
    expected_fixture = _required_mapping(
        scenario_input,
        "conversation_fixture",
        "scenario.input",
    )
    initial_context = _required_mapping(trace, "initial_context", "common trace")
    actual_fixture = _required_mapping(
        initial_context,
        "conversation_fixture",
        "common trace.initial_context",
    )

    for field in ("id", "version"):
        expected_value = _required_string(
            expected_fixture,
            field,
            "scenario.input.conversation_fixture",
        )
        actual_value = _required_string(
            actual_fixture,
            field,
            "common trace.initial_context.conversation_fixture",
        )
        if actual_value != expected_value:
            issues.append(
                EvaluationIssue(
                    f"input.conversation_fixture.{field}",
                    f"expected {expected_value!r}, observed {actual_value!r}",
                )
            )


def _evaluate_assistance(
    expected: ReadOnlyJsonObject,
    trace: ReadOnlyJsonObject,
    equivalence_rules: Sequence[EquivalenceRule],
    issues: list[EvaluationIssue],
) -> None:
    expected_assistance = _required_mapping(expected, "assistance", "scenario.expected")
    events = _events(trace)

    proposals: dict[str, list[ReadOnlyJsonObject]] = defaultdict(list)
    for event in events:
        if event.get("type") != "values_proposed":
            continue
        interaction_id = _required_string(
            event,
            "interaction_id",
            "common trace values_proposed event",
        )
        values = _required_mapping(
            event,
            "values",
            "common trace values_proposed event",
        )
        proposals[interaction_id].append(values)

    expected_proposal_interactions: set[str] = set()
    for interaction_id, raw_expectation in expected_assistance.items():
        if not isinstance(interaction_id, str):
            raise EvaluationInputError(
                "scenario.expected.assistance keys must be interaction IDs"
            )
        if not isinstance(raw_expectation, Mapping):
            raise EvaluationInputError(
                f"scenario.expected.assistance.{interaction_id} must be an object"
            )

        action_type = _required_string(
            raw_expectation,
            "type",
            f"scenario.expected.assistance.{interaction_id}",
        )
        path = f"expected.assistance.{interaction_id}"

        if action_type != "propose_values":
            raise EvaluationInputError(
                f"Unsupported assistance expectation {action_type!r} at {path}"
            )

        expected_proposal_interactions.add(interaction_id)
        expected_values = _required_mapping(raw_expectation, "values", path)
        actual = proposals.get(interaction_id, [])
        if len(actual) != 1:
            issues.append(
                EvaluationIssue(
                    path,
                    f"expected one values_proposed event, observed {len(actual)}",
                )
            )
            continue

        values_path = f"{path}.values"
        if not _equivalent(
            expected_values,
            actual[0],
            values_path,
            equivalence_rules,
        ):
            issues.append(
                EvaluationIssue(
                    values_path,
                    f"expected {_json(expected_values)}, observed {_json(actual[0])}",
                )
            )

    for interaction_id, observed in proposals.items():
        if interaction_id not in expected_proposal_interactions:
            issues.append(
                EvaluationIssue(
                    f"expected.assistance.{interaction_id}",
                    "unexpected values_proposed event: "
                    f"{_json(observed if len(observed) > 1 else observed[0])}",
                )
            )

    for event in events:
        if event.get("type") == "answer_presented":
            answer_interaction_id = event.get("interaction_id")
            suffix = (
                f" at {answer_interaction_id!r}"
                if isinstance(answer_interaction_id, str)
                else ""
            )
            issues.append(
                EvaluationIssue(
                    "expected.assistance",
                    f"unexpected answer_presented event{suffix}",
                )
            )


def _evaluate_journey(
    expected: ReadOnlyJsonObject,
    trace: ReadOnlyJsonObject,
    journey_id: str,
    equivalence_rules: Sequence[EquivalenceRule],
    issues: list[EvaluationIssue],
) -> None:
    expected_journey = _required_mapping(expected, "journey", "scenario.expected")

    raw_branch = expected_journey.get("branch")
    if raw_branch is not None:
        if not isinstance(raw_branch, str) or not raw_branch:
            raise EvaluationInputError(
                "scenario.expected.journey.branch must be a non-empty string"
            )
        _evaluate_branch(journey_id, raw_branch, trace, issues)

    raw_final = expected_journey.get("final")
    if raw_final is None:
        return
    if not isinstance(raw_final, Mapping):
        raise EvaluationInputError("scenario.expected.journey.final must be an object")

    expected_status = raw_final.get("status")
    if expected_status is not None and (
        not isinstance(expected_status, str) or not expected_status
    ):
        raise EvaluationInputError(
            "scenario.expected.journey.final.status must be a non-empty string"
        )

    expected_result = raw_final.get("result")
    if expected_result is not None and not isinstance(expected_result, Mapping):
        raise EvaluationInputError(
            "scenario.expected.journey.final.result must be an object"
        )

    if expected_status is None and expected_result is None:
        return

    finished = [
        event for event in _events(trace) if event.get("type") == "journey_finished"
    ]
    if len(finished) != 1:
        issues.append(
            EvaluationIssue(
                "expected.journey.final",
                f"expected one journey_finished event, observed {len(finished)}",
            )
        )
        return

    event = finished[0]
    if expected_status is not None:
        actual_status = event.get("status")
        if actual_status != expected_status:
            issues.append(
                EvaluationIssue(
                    "expected.journey.final.status",
                    f"expected {expected_status!r}, observed {actual_status!r}",
                )
            )

        run = _required_mapping(trace, "run", "common trace")
        run_status = run.get("status")
        if run_status != expected_status:
            issues.append(
                EvaluationIssue(
                    "run.status",
                    f"expected {expected_status!r}, observed {run_status!r}",
                )
            )

    if expected_result is not None:
        actual_result = event.get("result")
        result_path = "expected.journey.final.result"
        if not _equivalent(
            expected_result,
            actual_result,
            result_path,
            equivalence_rules,
        ):
            issues.append(
                EvaluationIssue(
                    result_path,
                    "expected "
                    f"{_json(expected_result)}, observed {_json(actual_result)}",
                )
            )


def _evaluate_branch(
    journey_id: str,
    expected_branch: str,
    trace: ReadOnlyJsonObject,
    issues: list[EvaluationIssue],
) -> None:
    journey_branches = _BRANCHES.get(journey_id)
    if journey_branches is None or expected_branch not in journey_branches:
        raise EvaluationInputError(
            f"No branch observation rule is defined for {journey_id!r} "
            f"branch {expected_branch!r}"
        )

    definition = journey_branches[expected_branch]
    observed_interactions = {
        event.get("interaction_id")
        for event in _events(trace)
        if event.get("type") == "interaction_available"
        and isinstance(event.get("interaction_id"), str)
    }

    missing = definition.required_interactions - observed_interactions
    forbidden = definition.forbidden_interactions & observed_interactions
    if missing or forbidden:
        details: list[str] = []
        if missing:
            details.append(f"missing interactions {sorted(missing)!r}")
        if forbidden:
            details.append(f"observed other-branch interactions {sorted(forbidden)!r}")
        issues.append(
            EvaluationIssue(
                "expected.journey.branch",
                f"expected {expected_branch!r}: {'; '.join(details)}",
            )
        )


def _evaluate_failures(
    trace: ReadOnlyJsonObject,
    issues: list[EvaluationIssue],
) -> None:
    failures = [
        event for event in _events(trace) if event.get("type") == "assistance_failed"
    ]
    for index, event in enumerate(failures, start=1):
        interaction_id = event.get("interaction_id")
        suffix = f" at {interaction_id!r}" if isinstance(interaction_id, str) else ""
        issues.append(
            EvaluationIssue(
                f"common_trace.assistance_failed[{index}]",
                f"assistance failed{suffix}",
            )
        )


def _equivalence_rules(scenario: ReadOnlyJsonObject) -> tuple[EquivalenceRule, ...]:
    raw_evaluation = scenario.get("evaluation")
    if raw_evaluation is None:
        return ()
    if not isinstance(raw_evaluation, Mapping):
        raise EvaluationInputError("scenario.evaluation must be an object")

    raw_rules = raw_evaluation.get("accepted_equivalence_rules", [])
    if not isinstance(raw_rules, list):
        raise EvaluationInputError(
            "scenario.evaluation.accepted_equivalence_rules must be a list"
        )

    rules: list[EquivalenceRule] = []
    for index, raw_rule in enumerate(raw_rules):
        path = f"scenario.evaluation.accepted_equivalence_rules[{index}]"
        if not isinstance(raw_rule, Mapping):
            raise EvaluationInputError(f"{path} must be an object")

        rule_type = _required_string(raw_rule, "type", path)
        target = _required_string(raw_rule, "target", path)
        raw_paths = raw_rule.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise EvaluationInputError(f"{path}.paths must be a non-empty list")
        if not all(isinstance(item, str) and item for item in raw_paths):
            raise EvaluationInputError(
                f"{path}.paths must contain only non-empty strings"
            )
        if rule_type != "unordered_text_components":
            raise EvaluationInputError(
                f"Unsupported equivalence rule type {rule_type!r} at {path}"
            )

        rules.append(
            EquivalenceRule(
                rule_type=rule_type,
                target=target,
                paths=tuple(raw_paths),
            )
        )
    return tuple(rules)


def _equivalent(
    expected: object,
    actual: object,
    target: str,
    rules: Sequence[EquivalenceRule],
) -> bool:
    applicable = [rule for rule in rules if rule.target == target]
    if not applicable:
        return actual == expected
    if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
        return False

    expected_copy: JsonObject = deepcopy(dict(expected))
    actual_copy: JsonObject = deepcopy(dict(actual))

    for rule in applicable:
        if rule.rule_type != "unordered_text_components":
            raise EvaluationInputError(
                f"Unsupported equivalence rule type {rule.rule_type!r}"
            )
        if not _unordered_text_components_equal(
            expected_copy,
            actual_copy,
            rule.paths,
        ):
            return False
        for path in rule.paths:
            _delete_path(expected_copy, path)
            _delete_path(actual_copy, path)

    return actual_copy == expected_copy


def _unordered_text_components_equal(
    expected: ReadOnlyJsonObject,
    actual: ReadOnlyJsonObject,
    paths: Sequence[str],
) -> bool:
    expected_tokens: Counter[str] = Counter()
    actual_tokens: Counter[str] = Counter()

    for path in paths:
        expected_value = _value_at_path(expected, path)
        actual_value = _value_at_path(actual, path)

        expected_part = _text_tokens(expected_value, expected=True, path=path)
        actual_part = _text_tokens(actual_value, expected=False, path=path)
        if actual_part is None:
            return False
        expected_tokens.update(expected_part)
        actual_tokens.update(actual_part)

    return expected_tokens == actual_tokens


def _text_tokens(
    value: object,
    *,
    expected: bool,
    path: str,
) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, str):
        if expected:
            raise EvaluationInputError(
                "unordered_text_components expected value at "
                f"{path!r} must be text or null"
            )
        return None
    return re.findall(r"\w+", value.casefold(), flags=re.UNICODE)


def _value_at_path(container: ReadOnlyJsonObject, path: str) -> object:
    current: object = container
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _delete_path(container: JsonObject, path: str) -> None:
    parts = path.split(".")
    current: JsonObject = container
    for part in parts[:-1]:
        value = current.get(part)
        if not isinstance(value, dict):
            return
        current = value
    current.pop(parts[-1], None)


def _events(trace: ReadOnlyJsonObject) -> list[ReadOnlyJsonObject]:
    raw_events = trace.get("events")
    if not isinstance(raw_events, list):
        raise EvaluationInputError("common trace events must be a list")

    events: list[ReadOnlyJsonObject] = []
    for index, event in enumerate(raw_events):
        if not isinstance(event, Mapping):
            raise EvaluationInputError(f"common trace event {index} must be an object")
        events.append(event)
    return events


def _require_version(
    document: ReadOnlyJsonObject,
    supported: str,
    label: str,
) -> None:
    version = _required_string(document, "schema_version", label)
    if version != supported:
        raise EvaluationInputError(
            f"Unsupported {label} schema version {version!r}; expected {supported!r}"
        )


def _required_mapping(
    container: ReadOnlyJsonObject,
    key: str,
    path: str,
) -> ReadOnlyJsonObject:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise EvaluationInputError(f"{path}.{key} must be an object")
    return value


def _required_string(
    container: ReadOnlyJsonObject,
    key: str,
    path: str,
) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise EvaluationInputError(f"{path}.{key} must be a non-empty string")
    return value


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
