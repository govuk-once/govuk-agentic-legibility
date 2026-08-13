"""Batch regression assertions for scenario/common-trace pairs."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agents.src.scenario_evaluation.evaluator import (
    EvaluationInputError,
    EvaluationResult,
    evaluate_common_trace,
    load_document,
)

SUPPORTED_MANIFEST_VERSION = "0.1"


@dataclass(frozen=True)
class BatchCase:
    """One scenario/common-trace assertion declared by a regression manifest."""

    case_id: str
    scenario_path: Path
    trace_path: Path
    expect_pass: bool


@dataclass(frozen=True)
class BatchCaseResult:
    """Observed evaluator result and whether it matched the manifest assertion."""

    case: BatchCase
    evaluation: EvaluationResult

    @property
    def passed(self) -> bool:
        """Return whether the observed evaluator outcome matched the expectation."""
        return self.evaluation.passed == self.case.expect_pass


def load_manifest(path: Path, *, root: Path) -> tuple[BatchCase, ...]:
    """Load a batch regression manifest.

    Manifest paths are resolved relative to ``root`` so the committed manifest can
    use stable repository-relative paths.

    Args:
        path: YAML or JSON manifest file.
        root: Base directory for scenario and trace paths in the manifest.

    Returns:
        Ordered batch cases from the manifest.

    Raises:
        EvaluationInputError: If the manifest is malformed or unsupported.
    """
    document = load_document(path)
    version = document.get("schema_version")
    if version != SUPPORTED_MANIFEST_VERSION:
        raise EvaluationInputError(
            "batch manifest schema_version must be "
            f"{SUPPORTED_MANIFEST_VERSION!r}, got {version!r}"
        )

    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvaluationInputError("batch manifest cases must be a non-empty list")

    cases: list[BatchCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        path_prefix = f"cases[{index}]"
        if not isinstance(raw_case, Mapping):
            raise EvaluationInputError(f"{path_prefix} must be an object")

        case_id = _required_string(raw_case, "id", path_prefix)
        if case_id in seen_ids:
            raise EvaluationInputError(f"duplicate batch case id {case_id!r}")
        seen_ids.add(case_id)

        scenario = _required_string(raw_case, "scenario", path_prefix)
        trace = _required_string(raw_case, "trace", path_prefix)
        expected = _required_string(raw_case, "expect", path_prefix)
        if expected not in {"pass", "fail"}:
            raise EvaluationInputError(
                f"{path_prefix}.expect must be 'pass' or 'fail', got {expected!r}"
            )

        cases.append(
            BatchCase(
                case_id=case_id,
                scenario_path=root / scenario,
                trace_path=root / trace,
                expect_pass=expected == "pass",
            )
        )

    return tuple(cases)


def evaluate_batch_case(case: BatchCase) -> BatchCaseResult:
    """Evaluate one manifest case using the shared common-trace evaluator."""
    scenario = load_document(case.scenario_path)
    trace = load_document(case.trace_path)
    evaluation = evaluate_common_trace(scenario, trace)
    return BatchCaseResult(case=case, evaluation=evaluation)


def main(argv: Sequence[str] | None = None) -> int:
    """Run every assertion in a batch regression manifest.

    Args:
        argv: Optional command-line arguments. Uses process arguments when omitted.

    Returns:
        Shell exit status: 0 when every assertion matches, 1 when at least one does
        not, and 2 for invalid evaluator or manifest input.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate a batch of known common traces against shared scenarios."
    )
    parser.add_argument("manifest", type=Path, help="Batch regression manifest")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Base directory for manifest paths (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show evaluator issues even when a failure was expected",
    )
    args = parser.parse_args(argv)

    try:
        cases = load_manifest(args.manifest, root=args.root)
        results = tuple(evaluate_batch_case(case) for case in cases)
    except EvaluationInputError as error:
        print(f"ERROR: {error}")
        return 2

    for result in results:
        _print_case_result(result, verbose=args.verbose)

    passed = sum(result.passed for result in results)
    failed = len(results) - passed
    print()
    print(f"{len(results)} cases: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def _print_case_result(result: BatchCaseResult, *, verbose: bool) -> None:
    """Print one assertion result without presenting expected failures as failures."""
    case = result.case
    evaluation = result.evaluation

    if result.passed:
        if evaluation.passed:
            print(f"PASS {case.case_id}")
            return

        print(f"PASS {case.case_id} (evaluation failed as expected)")
        if verbose:
            _print_issues(evaluation)
        return

    if case.expect_pass:
        print(f"FAIL {case.case_id}: expected evaluation to pass")
        _print_issues(evaluation)
    else:
        print(f"FAIL {case.case_id}: expected evaluation to fail, but it passed")


def _print_issues(result: EvaluationResult) -> None:
    """Print evaluator mismatch reasons under a batch assertion."""
    for issue in result.issues:
        print(f"  - {issue.path}: {issue.message}")


def _required_string(
    mapping: Mapping[object, object],
    key: str,
    path: str,
) -> str:
    """Return one required non-empty string from a manifest mapping."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise EvaluationInputError(f"{path}.{key} must be a non-empty string")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
