"""Capture the real SFSM interpreter state from a running Temporal workflow."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from temporalio.client import Client

from evaluation.scenario_case import (
    DEFAULT_SCENARIO_ROOT,
    checkpoint_target,
    load_document,
    resolve_scenario_path,
)

DEFAULT_TEMPORAL_ADDRESS = "localhost:7233"


def validate_target(
    checkpoint: dict[str, Any],
    *,
    expected_process: str | None,
    expected_state: str,
) -> None:
    """Fail if the captured workflow is not paused at the requested interaction."""
    actual_process, actual_state = checkpoint_target(checkpoint)

    if actual_state != expected_state or (
        expected_process is not None and actual_process != expected_process
    ):
        expected = (
            f"{expected_process}.{expected_state}"
            if expected_process is not None
            else expected_state
        )
        raise ValueError(
            "Workflow is not at the scenario checkpoint: "
            f"expected {expected}, got {actual_process}.{actual_state}"
        )

    awaiting = checkpoint.get("awaiting")
    if not isinstance(awaiting, dict) or awaiting.get("state_id") != expected_state:
        raise ValueError(
            "Workflow is not currently waiting for input at the scenario checkpoint"
        )


def _new_case_directory(scenario_reference: Path) -> Path:
    """Resolve where a not-yet-created scenario case should live.

    Missing relative references use the same ``evaluation/scenarios`` root as the
    runner. Absolute paths, and already-created explicit directories, are kept as
    supplied. A missing ``scenario.yaml`` path is also accepted for convenience.
    """
    reference = scenario_reference.expanduser()
    if reference.is_dir():
        return reference.resolve()

    if reference.is_absolute():
        candidate = reference
    else:
        candidate = DEFAULT_SCENARIO_ROOT / reference

    if candidate.name in {"scenario.yaml", "scenario.yml"}:
        candidate = candidate.parent
    return candidate.resolve()


def scenario_capture_target(
    scenario_reference: Path,
) -> tuple[Path, str | None, str | None]:
    """Resolve capture output and, when possible, its expected semantic target.

    Capture is intentionally allowed before ``scenario.yaml`` exists. In that
    case the reference names the future case directory, and ``checkpoint.json``
    is written there without target validation.
    """
    try:
        scenario_path = resolve_scenario_path(scenario_reference)
        case_directory = scenario_path.parent
    except FileNotFoundError:
        scenario_path = None
        case_directory = _new_case_directory(scenario_reference)

    checkpoint_path = case_directory / "checkpoint.json"

    if checkpoint_path.is_file():
        process_id, state_id = checkpoint_target(load_document(checkpoint_path))
        return checkpoint_path, process_id, state_id

    if scenario_path is None:
        return checkpoint_path, None, None

    # If the scenario already exists but the checkpoint does not, a single
    # expected submission still gives us the state ID for partial validation.
    scenario = load_document(scenario_path)
    submissions = scenario.get("expected", {}).get("submissions")
    if isinstance(submissions, dict) and len(submissions) == 1:
        state_id = next(iter(submissions))
        if isinstance(state_id, str) and state_id:
            return checkpoint_path, None, state_id

    return checkpoint_path, None, None


async def capture(args: argparse.Namespace) -> int:
    """Query one running workflow and write its semantic interpreter checkpoint."""
    output = args.output
    expected_process: str | None = None
    expected_state: str | None = None

    if args.scenario is not None:
        conventional_output, expected_process, expected_state = scenario_capture_target(
            args.scenario
        )
        if output is None:
            output = conventional_output

    if output is None:
        raise ValueError("--output is required when --scenario is not supplied")

    client = await Client.connect(args.temporal_address)
    handle = client.get_workflow_handle(args.workflow_id)
    checkpoint = await handle.query("evaluation_checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("evaluation_checkpoint query returned a non-object")

    if expected_state is not None:
        validate_target(
            checkpoint,
            expected_process=expected_process,
            expected_state=expected_state,
        )

    document = {
        "source_workflow_id": args.workflow_id,
        **checkpoint,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    current = checkpoint.get("current_state", {})
    frames = checkpoint.get("interpreter_state", {}).get("frames", [])
    print(
        f"Captured {len(frames)} frame(s) at "
        f"{current.get('process_id')}.{current.get('state_id')} "
        f"to {output}"
    )
    if args.scenario is not None and not (output.parent / "scenario.yaml").is_file():
        print(
            "Created checkpoint for a new scenario case. Add scenario.yaml and "
            "conversation.json before running the eval."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a semantic InterpreterState snapshot from a running "
            "SFSMInterpreter workflow."
        )
    )
    parser.add_argument("workflow_id")
    parser.add_argument(
        "--scenario",
        type=Path,
        help=(
            "Scenario case directory or path relative to evaluation/scenarios. "
            "When supplied, checkpoint.json is the default output and the target "
            "interaction is validated where possible."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit output path (required only when --scenario is omitted).",
    )
    parser.add_argument(
        "--temporal-address",
        default=os.environ.get("TEMPORAL_ADDRESS", DEFAULT_TEMPORAL_ADDRESS),
    )
    return asyncio.run(capture(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
