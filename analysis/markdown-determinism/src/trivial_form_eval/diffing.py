import difflib
from typing import Any

from trivial_form_eval.jsonutil import pretty_json


def field_differences(expected: Any, actual: Any, path: str = "") -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() - actual.keys()):
            differences.append(
                {"path": join_path(path, key), "kind": "missing_field", "expected": expected[key]}
            )
        for key in sorted(actual.keys() - expected.keys()):
            differences.append(
                {"path": join_path(path, key), "kind": "unexpected_field", "actual": actual[key]}
            )
        for key in sorted(expected.keys() & actual.keys()):
            differences.extend(field_differences(expected[key], actual[key], join_path(path, key)))
        return differences

    if type(expected) is not type(actual):
        differences.append(
            {
                "path": path,
                "kind": "incorrect_type",
                "expected": expected,
                "actual": actual,
                "expected_type": type(expected).__name__,
                "actual_type": type(actual).__name__,
            }
        )
        return differences

    if expected != actual:
        differences.append(
            {"path": path, "kind": "incorrect_value", "expected": expected, "actual": actual}
        )
    return differences


def join_path(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def unified_json_diff(expected: Any, actual: Any) -> str:
    expected_lines = pretty_json(expected).splitlines(keepends=True)
    actual_lines = pretty_json(actual).splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(expected_lines, actual_lines, fromfile="expected", tofile="actual")
    )
