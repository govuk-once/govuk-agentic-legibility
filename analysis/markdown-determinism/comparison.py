import string
from typing import Any

from trivial_form_eval.diffing import field_differences
from trivial_form_eval.jsonutil import canonical_json

DEFAULT_EVALUATION_CONFIG: dict[str, Any] = {"accepted_equivalence_rules": []}
LEGACY_CONTACT_EVALUATION_CONFIG: dict[str, Any] = {
    "accepted_equivalence_rules": [
        {
            "type": "unordered_text_components",
            "paths": ["address.address_line_1", "address.address_line_2"],
        }
    ]
}
SUPPORTED_RULE_TYPES = {"unordered_text_components"}


def normalise_evaluation_config(value: Any) -> dict[str, Any]:
    if value is None:
        return {"accepted_equivalence_rules": []}
    if not isinstance(value, dict):
        raise ValueError("evaluation.json must contain a JSON object.")

    unknown_keys = set(value) - {"accepted_equivalence_rules"}
    if unknown_keys:
        raise ValueError("Unknown evaluation.json keys: " + ", ".join(sorted(unknown_keys)))

    rules = value.get("accepted_equivalence_rules", [])
    if not isinstance(rules, list):
        raise ValueError("accepted_equivalence_rules must be a JSON array.")

    normalised_rules = [normalise_rule(rule, index) for index, rule in enumerate(rules)]
    return {"accepted_equivalence_rules": normalised_rules}


def normalise_rule(rule: Any, index: int) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise ValueError(f"Equivalence rule {index + 1} must be a JSON object.")

    unknown_keys = set(rule) - {"type", "paths"}
    if unknown_keys:
        raise ValueError(
            f"Unknown keys in equivalence rule {index + 1}: " + ", ".join(sorted(unknown_keys))
        )

    rule_type = rule.get("type")
    if rule_type not in SUPPORTED_RULE_TYPES:
        raise ValueError(
            f"Equivalence rule {index + 1} has unsupported type {rule_type!r}. "
            f"Supported types: {', '.join(sorted(SUPPORTED_RULE_TYPES))}."
        )

    paths = rule.get("paths")
    if (
        not isinstance(paths, list)
        or len(paths) < 2
        or not all(isinstance(path, str) and path for path in paths)
    ):
        raise ValueError(f"Equivalence rule {index + 1} must contain at least two non-empty paths.")
    if len(set(paths)) != len(paths):
        raise ValueError(f"Equivalence rule {index + 1} contains duplicate paths.")

    return {"type": rule_type, "paths": paths}


def accepted_match(
    expected: dict[str, Any],
    actual: dict[str, Any],
    evaluation_config: dict[str, Any] | None = None,
) -> bool:
    if canonical_json(expected) == canonical_json(actual):
        return True

    config = normalise_evaluation_config(evaluation_config)
    difference_paths = {difference["path"] for difference in field_differences(expected, actual)}
    if not difference_paths:
        return True

    covered_paths: set[str] = set()
    for rule in config["accepted_equivalence_rules"]:
        paths = set(rule["paths"])
        relevant_differences = difference_paths & paths
        if not relevant_differences:
            continue

        if rule["type"] == "unordered_text_components" and unordered_text_components_equivalent(
            expected, actual, rule["paths"]
        ):
            covered_paths.update(relevant_differences)

    return difference_paths <= covered_paths


def unordered_text_components_equivalent(
    expected: dict[str, Any], actual: dict[str, Any], paths: list[str]
) -> bool:
    expected_components = [value_at_path(expected, path) for path in paths]
    actual_components = [value_at_path(actual, path) for path in paths]

    if not all(isinstance(component, str) and component for component in expected_components):
        return False
    if not all(isinstance(component, str) for component in actual_components):
        return False

    remainder = " ".join(actual_components)
    for component in sorted(expected_components, key=len, reverse=True):
        index = remainder.find(component)
        if index == -1:
            return False
        remainder = remainder[:index] + remainder[index + len(component) :]

    return all(character.isspace() or character in string.punctuation for character in remainder)


def value_at_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
