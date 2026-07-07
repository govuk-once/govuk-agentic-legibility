import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from trivial_form_eval.comparison import (
    LEGACY_CONTACT_EVALUATION_CONFIG,
    accepted_match,
    normalise_evaluation_config,
)
from trivial_form_eval.diffing import field_differences, unified_json_diff
from trivial_form_eval.jsonutil import canonical_json, pretty_json

STATUSES = [
    "correct",
    "incorrect_arguments",
    "schema_invalid_arguments",
    "malformed_arguments",
    "no_tool_call",
    "wrong_tool",
    "multiple_tool_calls",
    "refusal_or_prose_only",
    "transient_api_failure_exhausted",
    "non_transient_api_failure",
    "unexpected_response",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def analyse_run_dir(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    expected = json.loads((run_dir / "expected_arguments.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    evaluation_config = load_saved_evaluation_config(run_dir)
    records = apply_current_comparison_policy(
        read_jsonl(run_dir / "responses.jsonl"),
        expected,
        evaluation_config,
    )
    summary = build_summary(records, expected, manifest.get("requested_runs", len(records)))
    variants = build_variants(records, expected, evaluation_config)
    differences = build_differences_report(records, expected, variants, summary)
    return summary, variants, differences


def load_saved_evaluation_config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "evaluation.json"
    if not path.exists():
        # Runs created before fixture-level policies existed can only be contact
        # runs, so retain their historical address-line equivalence behaviour.
        return normalise_evaluation_config(LEGACY_CONTACT_EVALUATION_CONFIG)
    return normalise_evaluation_config(json.loads(path.read_text(encoding="utf-8")))


def apply_current_comparison_policy(
    records: list[dict[str, Any]],
    expected: dict[str, Any],
    evaluation_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    updated_records = []
    expected_canonical = canonical_json(expected)

    for record in records:
        updated = dict(record)
        if updated.get("schema_valid") and isinstance(updated.get("parsed_tool_arguments"), dict):
            actual = updated["parsed_tool_arguments"]
            updated["exact_match_to_expected"] = (
                updated.get("canonical_tool_arguments") == expected_canonical
            )
            updated["accepted_match_to_expected"] = accepted_match(
                expected,
                actual,
                evaluation_config,
            )
            updated["status"] = (
                "correct" if updated["accepted_match_to_expected"] else "incorrect_arguments"
            )
            if updated["accepted_match_to_expected"]:
                updated.pop("field_differences", None)
                updated.pop("unified_diff", None)
            else:
                updated["field_differences"] = field_differences(expected, actual)
                updated["unified_diff"] = unified_json_diff(expected, actual)
        updated_records.append(updated)

    return updated_records


def build_summary(
    records: list[dict[str, Any]], expected: dict[str, Any], requested_runs: int
) -> dict[str, Any]:
    completed = len(records)
    status_counts = Counter(record["status"] for record in records)
    raw_values = [
        raw
        for record in records
        for raw in record.get("raw_tool_argument_strings", [])
        if isinstance(raw, str)
    ]
    canonical_values = [
        record["canonical_tool_arguments"]
        for record in records
        if record.get("schema_valid") and record.get("canonical_tool_arguments")
    ]
    raw_counts = Counter(raw_values)
    canonical_counts = Counter(canonical_values)

    field_counts: Counter[str] = Counter()
    for record in records:
        if record.get("schema_valid") and not record.get("accepted_match_to_expected"):
            for diff in field_differences(expected, record["parsed_tool_arguments"]):
                field_counts[diff["path"]] += 1

    api_failure_count = (
        status_counts["transient_api_failure_exhausted"]
        + status_counts["non_transient_api_failure"]
    )
    schema_invalid_count = status_counts["schema_invalid_arguments"]
    malformed_count = status_counts["malformed_arguments"]
    correct_count = status_counts["correct"]
    schema_valid_count = sum(1 for record in records if record.get("schema_valid"))
    tool_compliance_count = sum(
        1 for record in records if record.get("exactly_one_correct_tool_call")
    )
    exact_match_count = sum(1 for record in records if record.get("exact_match_to_expected"))
    accepted_match_count = sum(1 for record in records if record.get("accepted_match_to_expected"))
    incorrect_semantic_count = status_counts["incorrect_arguments"]
    modal_raw = raw_counts.most_common(1)[0] if raw_counts else (None, 0)
    modal_canonical = canonical_counts.most_common(1)[0] if canonical_counts else (None, 0)
    outcome_denominator = completed

    return {
        "requested_runs": requested_runs,
        "completed_runs": completed,
        "completion_rate": rate(completed, requested_runs),
        "rate_denominator": "completed_runs",
        "status_counts": {status: status_counts[status] for status in STATUSES},
        "correct_count": correct_count,
        "correct_rate": rate(correct_count, outcome_denominator),
        "exact_expected_match_count": exact_match_count,
        "exact_expected_match_rate": rate(exact_match_count, outcome_denominator),
        "accepted_expected_match_count": accepted_match_count,
        "accepted_expected_match_rate": rate(accepted_match_count, outcome_denominator),
        "schema_valid_count": schema_valid_count,
        "schema_valid_rate": rate(schema_valid_count, outcome_denominator),
        "exactly_one_correct_tool_call_count": tool_compliance_count,
        "exactly_one_correct_tool_call_rate": rate(tool_compliance_count, outcome_denominator),
        "no_tool_call_count": status_counts["no_tool_call"],
        "no_tool_call_rate": rate(status_counts["no_tool_call"], outcome_denominator),
        "wrong_tool_count": status_counts["wrong_tool"],
        "wrong_tool_rate": rate(status_counts["wrong_tool"], outcome_denominator),
        "multiple_tool_call_count": status_counts["multiple_tool_calls"],
        "multiple_tool_call_rate": rate(status_counts["multiple_tool_calls"], outcome_denominator),
        "malformed_arguments_count": malformed_count,
        "malformed_arguments_rate": rate(malformed_count, outcome_denominator),
        "schema_invalid_count": schema_invalid_count,
        "schema_invalid_rate": rate(schema_invalid_count, outcome_denominator),
        "semantically_incorrect_count": incorrect_semantic_count,
        "semantically_incorrect_rate": rate(incorrect_semantic_count, outcome_denominator),
        "api_failure_count": api_failure_count,
        "api_failure_rate": rate(api_failure_count, outcome_denominator),
        "unique_raw_tool_argument_strings": len(raw_counts),
        "unique_canonical_valid_argument_objects": len(canonical_counts),
        "modal_raw_argument_string": modal_raw[0],
        "modal_raw_argument_string_count": modal_raw[1],
        "modal_raw_argument_string_proportion": rate(modal_raw[1], len(raw_values)),
        "modal_canonical_valid_argument_object": modal_canonical[0],
        "modal_canonical_valid_argument_object_count": modal_canonical[1],
        "modal_canonical_valid_argument_object_proportion": rate(
            modal_canonical[1], len(canonical_values)
        ),
        "all_successful_raw_tool_argument_strings_identical": len(raw_counts) <= 1,
        "all_schema_valid_parsed_outputs_semantically_identical": len(canonical_counts) <= 1,
        "all_requested_runs_completed": completed == requested_runs,
        "every_requested_run_correct": completed == requested_runs
        and correct_count == requested_runs,
        "latency_summary": number_summary(
            [
                record["latency_seconds"]
                for record in records
                if record.get("latency_seconds") is not None
            ]
        ),
        "token_usage_summary": token_usage_summary(records),
        "cost_summary": number_summary(
            [
                record["estimated_cost"]
                for record in records
                if isinstance(record.get("estimated_cost"), int | float)
            ]
        ),
        "field_level_mismatch_counts": dict(sorted(field_counts.items())),
    }


def build_variants(
    records: list[dict[str, Any]],
    expected: dict[str, Any],
    evaluation_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_canonical = canonical_json(expected)
    by_canonical: dict[str, list[dict[str, Any]]] = defaultdict(list)
    non_valid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed_raw: Counter[str] = Counter()

    for record in records:
        if record.get("schema_valid") and record.get("canonical_tool_arguments"):
            by_canonical[record["canonical_tool_arguments"]].append(record)
        else:
            non_valid[record["status"]].append(record)
            if record["status"] == "malformed_arguments":
                for raw in record.get("raw_tool_argument_strings", []):
                    if isinstance(raw, str):
                        malformed_raw[raw] += 1

    variants = []
    total = len(records)
    for index, canonical in enumerate(sorted(by_canonical), start=1):
        group = by_canonical[canonical]
        parsed = group[0]["parsed_tool_arguments"]
        raw_strings = [
            raw
            for record in group
            for raw in record.get("raw_tool_argument_strings", [])
            if isinstance(raw, str)
        ]
        variants.append(
            {
                "variant_id": f"variant_{index:03d}",
                "canonical_argument_string": canonical,
                "pretty_printed_argument_string": pretty_json(parsed),
                "parsed_argument_object": parsed,
                "occurrence_count": len(group),
                "occurrence_proportion": rate(len(group), total),
                "example_run_numbers": [record["run_number"] for record in group[:5]],
                "exactly_matches_expected": canonical == expected_canonical,
                "accepted_match_to_expected": (
                    accepted_match(expected, parsed, evaluation_config)
                    if evaluation_config is not None
                    else bool(group[0].get("accepted_match_to_expected"))
                ),
                "field_level_differences_from_expected": field_differences(expected, parsed),
                "unified_text_diff_from_expected": unified_json_diff(expected, parsed),
                "distinct_raw_string_count": len(set(raw_strings)),
                "example_raw_argument_strings": list(dict.fromkeys(raw_strings))[:5],
            }
        )

    return {
        "variants": variants,
        "non_valid_outcome_categories": {
            status: {
                "count": len(group),
                "example_run_numbers": [record["run_number"] for record in group[:5]],
            }
            for status, group in sorted(non_valid.items())
        },
        "malformed_argument_strings": [
            {"raw_argument_string": raw, "count": count}
            for raw, count in malformed_raw.most_common()
        ],
    }


def build_differences_report(
    records: list[dict[str, Any]],
    expected: dict[str, Any],
    variants: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# Form Evaluation Differences",
        "",
        "## Expected arguments",
        "",
        pretty_json(expected),
        "",
        "## Accepted non-exact semantic variants",
        "",
    ]

    for variant in variants["variants"]:
        if variant["exactly_matches_expected"] or not variant["accepted_match_to_expected"]:
            continue
        add_variant_report(lines, variant)

    lines.extend(["## Incorrect semantic variants", ""])
    for variant in variants["variants"]:
        if variant["accepted_match_to_expected"]:
            continue
        add_variant_report(lines, variant)

    lines.extend(["## Non-valid and API outcomes", ""])
    for status in [
        "malformed_arguments",
        "schema_invalid_arguments",
        "no_tool_call",
        "wrong_tool",
        "multiple_tool_calls",
        "refusal_or_prose_only",
        "transient_api_failure_exhausted",
        "non_transient_api_failure",
        "unexpected_response",
    ]:
        group = [record for record in records if record["status"] == status]
        lines.extend(
            [
                f"### {status}",
                "",
                f"Count: {len(group)}",
                f"Example runs: {[record['run_number'] for record in group[:5]]}",
                "",
            ]
        )
        if status in {"malformed_arguments", "schema_invalid_arguments"}:
            examples = [
                {
                    "run_number": record["run_number"],
                    "raw_tool_argument_strings": record.get("raw_tool_argument_strings"),
                    "errors": record.get("errors"),
                }
                for record in group[:5]
            ]
            lines.extend([pretty_json(examples), ""])

    lines.extend(["## Summary", "", pretty_json(summary), ""])
    return "\n".join(lines)


def add_variant_report(lines: list[str], variant: dict[str, Any]) -> None:
    lines.extend(
        [
            f"### {variant['variant_id']}",
            "",
            (
                f"Occurrences: {variant['occurrence_count']} "
                f"({variant['occurrence_proportion']:.2%})"
            ),
            f"Example runs: {variant['example_run_numbers']}",
            f"Accepted match: {variant['accepted_match_to_expected']}",
            f"Exact match: {variant['exactly_matches_expected']}",
            "",
            "Field-level differences:",
            pretty_json(variant["field_level_differences_from_expected"]),
            "",
            "Unified diff:",
            variant["unified_text_diff_from_expected"] or "(no diff)",
            "",
            "Example raw strings:",
            pretty_json(variant["example_raw_argument_strings"]),
            "",
        ]
    )


def rate(count: int, denominator: int) -> float:
    return count / denominator if denominator else 0.0


def number_summary(values: list[int | float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


def token_usage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    count = 0
    for record in records:
        usage = record.get("token_usage")
        if not isinstance(usage, dict):
            continue
        count += 1
        for key, value in usage.items():
            if isinstance(value, int | float):
                totals[key] += value
    return {"count": count, "totals": dict(totals)}
