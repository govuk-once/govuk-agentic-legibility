"""Capture the real SFSM interpreter state from a running Temporal workflow."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import yaml
from temporalio.client import Client

DEFAULT_TEMPORAL_ADDRESS = "localhost:7233"


def load_document(path: Path) -> dict[str, Any]:
    """Load a JSON or YAML object."""
    text = path.read_text(encoding="utf-8")
    value = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def expected_target(scenario: dict[str, Any]) -> tuple[str, str]:
    """Return the process/state pair declared by a targeted eval scenario."""
    checkpoint = scenario["input"]["checkpoint"]
    return checkpoint["process_id"], checkpoint["state_id"]


def validate_target(
    checkpoint: dict[str, Any], *, expected_process: str, expected_state: str
) -> None:
    """Fail if the captured workflow is not paused at the requested interaction."""
    current = checkpoint.get("current_state")
    if not isinstance(current, dict):
        raise ValueError("Workflow checkpoint did not contain current_state")

    actual = (current.get("process_id"), current.get("state_id"))
    expected = (expected_process, expected_state)
    if actual != expected:
        raise ValueError(
            "Workflow is not at the scenario checkpoint: "
            f"expected {expected_process}.{expected_state}, "
            f"got {actual[0]}.{actual[1]}"
        )

    awaiting = checkpoint.get("awaiting")
    if not isinstance(awaiting, dict) or awaiting.get("state_id") != expected_state:
        raise ValueError(
            "Workflow is not currently waiting for input at the scenario checkpoint"
        )


async def capture(args: argparse.Namespace) -> int:
    """Query one running workflow and write its semantic interpreter checkpoint."""
    client = await Client.connect(args.temporal_address)
    handle = client.get_workflow_handle(args.workflow_id)
    checkpoint = await handle.query("evaluation_checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("evaluation_checkpoint query returned a non-object")

    if args.scenario is not None:
        process_id, state_id = expected_target(load_document(args.scenario))
        validate_target(
            checkpoint,
            expected_process=process_id,
            expected_state=state_id,
        )

    document = {
        "source_workflow_id": args.workflow_id,
        **checkpoint,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    current = checkpoint.get("current_state", {})
    frames = checkpoint.get("interpreter_state", {}).get("frames", [])
    print(
        f"Captured {len(frames)} frame(s) at "
        f"{current.get('process_id')}.{current.get('state_id')} "
        f"to {args.output}"
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        type=Path,
        help="Optional scenario used to verify the workflow is at the target state.",
    )
    parser.add_argument(
        "--temporal-address",
        default=os.environ.get("TEMPORAL_ADDRESS", DEFAULT_TEMPORAL_ADDRESS),
    )
    return asyncio.run(capture(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
