"""Resolve self-contained durable evaluation scenario cases."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

EVALUATION_ROOT = Path(__file__).resolve().parent
DEFAULT_SCENARIO_ROOT = EVALUATION_ROOT / "scenarios"


@dataclass(frozen=True)
class ScenarioCase:
    """The three colocated documents that define one durable evaluation case."""

    directory: Path
    scenario_path: Path
    conversation_path: Path
    checkpoint_path: Path
    scenario: dict[str, Any]
    conversation: dict[str, Any]
    checkpoint: dict[str, Any]

    @property
    def target(self) -> tuple[str, str]:
        """Return the process/state pair captured by the checkpoint."""
        return checkpoint_target(self.checkpoint)


def load_document(path: Path) -> dict[str, Any]:
    """Load a JSON or YAML object."""
    text = path.read_text(encoding="utf-8")
    value = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def resolve_scenario_path(reference: Path) -> Path:
    """Resolve a scenario case reference to its ``scenario.yaml`` file.

    References may be an explicit YAML path/directory or a path relative to
    ``evaluation/scenarios`` such as
    ``maternity_allowance/work_status_fixed_term_contract_ended``.
    """
    reference = reference.expanduser()
    candidates = [reference, DEFAULT_SCENARIO_ROOT / reference]

    for candidate in candidates:
        if candidate.is_dir():
            scenario_path = candidate / "scenario.yaml"
            if scenario_path.is_file():
                return scenario_path.resolve()
        if candidate.is_file():
            return candidate.resolve()

    expected = DEFAULT_SCENARIO_ROOT / reference / "scenario.yaml"
    raise FileNotFoundError(
        f"Could not resolve scenario {reference!s}; expected a case directory "
        f"containing scenario.yaml (for example {expected})"
    )


def checkpoint_target(checkpoint: dict[str, Any]) -> tuple[str, str]:
    """Return the current process/state encoded in a captured checkpoint."""
    current = checkpoint.get("current_state")
    if not isinstance(current, dict):
        raise ValueError("Captured checkpoint is missing current_state")

    process_id = current.get("process_id")
    state_id = current.get("state_id")
    if not isinstance(process_id, str) or not process_id:
        raise ValueError("Captured checkpoint current_state is missing process_id")
    if not isinstance(state_id, str) or not state_id:
        raise ValueError("Captured checkpoint current_state is missing state_id")
    return process_id, state_id


def load_scenario_case(reference: Path) -> ScenarioCase:
    """Load and validate one self-contained durable evaluation case."""
    scenario_path = resolve_scenario_path(reference)
    directory = scenario_path.parent
    conversation_path = directory / "conversation.json"
    checkpoint_path = directory / "checkpoint.json"

    missing = [
        path.name
        for path in (conversation_path, checkpoint_path)
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Scenario case {directory} is missing required file(s): "
            + ", ".join(missing)
        )

    scenario = load_document(scenario_path)
    conversation = load_document(conversation_path)
    checkpoint = load_document(checkpoint_path)

    scenario_id = scenario.get("id")
    conversation_id = conversation.get("id")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise ValueError("Scenario requires a non-empty id")
    if conversation_id != scenario_id:
        raise ValueError(
            "conversation.json id must match scenario id: "
            f"expected {scenario_id!r}, got {conversation_id!r}"
        )

    journey_id = scenario.get("journey_id")
    if not isinstance(journey_id, str) or not journey_id:
        raise ValueError("Scenario requires a non-empty journey_id")
    if conversation.get("journey_id") != journey_id:
        raise ValueError("conversation.json journey_id does not match scenario")

    version = conversation.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("conversation.json requires a non-empty version")

    process_id, state_id = checkpoint_target(checkpoint)
    submissions = scenario.get("expected", {}).get("submissions")
    if isinstance(submissions, dict) and submissions and state_id not in submissions:
        raise ValueError(
            "Scenario expected.submissions does not target the checkpoint state: "
            f"{process_id}.{state_id}"
        )

    return ScenarioCase(
        directory=directory,
        scenario_path=scenario_path,
        conversation_path=conversation_path,
        checkpoint_path=checkpoint_path,
        scenario=scenario,
        conversation=conversation,
        checkpoint=checkpoint,
    )
