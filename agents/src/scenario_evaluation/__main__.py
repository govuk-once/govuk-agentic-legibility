"""Command-line entry point for common-trace scenario evaluation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from agents.src.scenario_evaluation.evaluator import (
    EvaluationInputError,
    EvaluationResult,
    evaluate_common_trace,
    load_document,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Evaluate one common trace against one scenario.

    Args:
        argv: Optional command-line arguments. Uses process arguments when omitted.

    Returns:
        Shell exit status: 0 when the observed evaluation matches ``--expect``, 1
        when it does not, and 2 for invalid evaluator input.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate a common trace against a scenario's expected behaviour."
    )
    parser.add_argument("scenario", type=Path, help="Scenario YAML file")
    parser.add_argument("trace", type=Path, help="Common trace YAML or JSON file")
    parser.add_argument(
        "--expect",
        choices=("pass", "fail"),
        default="pass",
        help=(
            "Expected evaluation outcome. Use 'fail' when asserting that a known "
            "non-compliant trace is rejected."
        ),
    )
    args = parser.parse_args(argv)

    try:
        scenario = load_document(args.scenario)
        trace = load_document(args.trace)
        result = evaluate_common_trace(scenario, trace)
    except EvaluationInputError as error:
        print(f"ERROR: {error}")
        return 2

    expected_pass = args.expect == "pass"
    if result.passed == expected_pass:
        if result.passed:
            print(f"PASS {result.scenario_id}: {args.trace}")
        else:
            print(
                f"PASS {result.scenario_id}: evaluation failed as expected: "
                f"{args.trace}"
            )
            _print_issues(result)
        return 0

    if expected_pass:
        print(f"FAIL {result.scenario_id}: {args.trace}")
        _print_issues(result)
    else:
        print(
            f"FAIL {result.scenario_id}: expected evaluation to fail, but it passed: "
            f"{args.trace}"
        )
    return 1


def _print_issues(result: EvaluationResult) -> None:
    """Print evaluator mismatch reasons beneath the overall assertion result."""
    for issue in result.issues:
        print(f"  - {issue.path}: {issue.message}")


if __name__ == "__main__":
    raise SystemExit(main())
