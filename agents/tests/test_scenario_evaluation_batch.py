"""Tests for batch regression assertions over common traces."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.src.scenario_evaluation.batch import main as batch_main

REPO_ROOT = Path(__file__).resolve().parents[2]
REGRESSION_MANIFEST = (
    REPO_ROOT / "agents/evaluation/regression/common-trace-examples.yaml"
)


def test_batch_cli_treats_expected_evaluation_failure_as_a_pass(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Batch assertions distinguish evaluator failure from regression failure."""
    _write_branch_scenario(tmp_path / "scenario.yaml")
    _write_branch_trace(tmp_path / "manual.common.yaml", "enter_address_manually")
    _write_branch_trace(tmp_path / "postcode.common.yaml", "find_address_by_postcode")
    (tmp_path / "manifest.yaml").write_text(
        """\
schema_version: "0.1"
cases:
  - id: "known-pass"
    scenario: "scenario.yaml"
    trace: "manual.common.yaml"
    expect: "pass"
  - id: "known-failure"
    scenario: "scenario.yaml"
    trace: "postcode.common.yaml"
    expect: "fail"
""",
        encoding="utf-8",
    )

    exit_code = batch_main(
        [str(tmp_path / "manifest.yaml"), "--root", str(tmp_path)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS known-pass" in output
    assert "PASS known-failure (evaluation failed as expected)" in output
    assert "2 cases: 2 passed, 0 failed" in output
    assert "\nFAIL " not in output


def test_batch_cli_fails_when_asserted_failure_unexpectedly_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A batch case fails if its expected evaluator outcome changes."""
    _write_branch_scenario(tmp_path / "scenario.yaml")
    _write_branch_trace(tmp_path / "manual.common.yaml", "enter_address_manually")
    (tmp_path / "manifest.yaml").write_text(
        """\
schema_version: "0.1"
cases:
  - id: "expected-rejection"
    scenario: "scenario.yaml"
    trace: "manual.common.yaml"
    expect: "fail"
""",
        encoding="utf-8",
    )

    exit_code = batch_main(
        [str(tmp_path / "manifest.yaml"), "--root", str(tmp_path)]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert (
        "FAIL expected-rejection: expected evaluation to fail, but it passed" in output
    )
    assert "1 cases: 0 passed, 1 failed" in output


def test_committed_common_trace_regression_manifest_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Known compliant and historical traces retain their asserted outcomes."""
    exit_code = batch_main(
        [str(REGRESSION_MANIFEST), "--root", str(REPO_ROOT)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS manual-entry-compliant" in output
    assert "PASS postcode-lookup-compliant" in output
    assert "PASS manual-entry-historical (evaluation failed as expected)" in output
    assert "PASS postcode-lookup-historical (evaluation failed as expected)" in output
    assert "4 cases: 4 passed, 0 failed" in output


def _write_branch_scenario(path: Path) -> None:
    """Write a minimal branch-only scenario."""
    path.write_text(
        """\
schema_version: "0.1"
id: "branch-only"
journey_id: "change-driving-licence-address"
input:
  conversation_fixture:
    id: "fixture"
    version: "1"
expected:
  journey:
    branch: "manual_entry"
""",
        encoding="utf-8",
    )


def _write_branch_trace(path: Path, interaction_id: str) -> None:
    """Write a minimal common trace that traverses one address-entry interaction."""
    path.write_text(
        f"""\
schema_version: "0.1"
source_trace: "test.jsonl"
run:
  id: "run"
  journey_id: "change-driving-licence-address"
  implementation: "test"
  status: "incomplete"
initial_context:
  conversation_fixture:
    id: "fixture"
    version: "1"
    sha256: "test"
events:
  - type: "interaction_available"
    interaction_id: "{interaction_id}"
""",
        encoding="utf-8",
    )
