"""Validate orchestration evaluation scenarios against the Forms catalogue.

From the repository root:
    uv run python -m forms_search.evals.validate
"""

from collections import Counter
import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = EVALS_DIR.parent / "data" / "catalogue.json"
SCENARIOS_PATH = EVALS_DIR / "scenarios.json"
OUTCOMES = {"offer_journey", "clarify", "no_journey"}
SEARCH_BEHAVIOURS = {"required", "forbidden"}


def validate() -> None:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]
    catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))["workflows"]
    workflow_ids = {form["workflow_id"] for form in catalogue}
    errors = []
    seen_ids = set()

    for index, scenario in enumerate(scenarios):
        location = f"scenarios[{index}]"
        if not isinstance(scenario, dict) or set(scenario) != {
            "id", "category", "search", "turns"
        }:
            errors.append(f"{location}: expected id, category, search, turns")
            continue

        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            errors.append(f"{location}: id must be a non-empty string")
        elif scenario_id in seen_ids:
            errors.append(f"{location}: duplicate id {scenario_id!r}")
        seen_ids.add(scenario_id)

        if not isinstance(scenario["category"], str) or not scenario["category"].strip():
            errors.append(f"{location}: category must be a non-empty string")
        if scenario["search"] not in SEARCH_BEHAVIOURS:
            errors.append(f"{location}: search must be required or forbidden")
        turns = scenario["turns"]
        if not isinstance(turns, list) or not turns:
            errors.append(f"{location}: turns must be a non-empty list")
            continue

        for turn_index, turn in enumerate(turns):
            turn_location = f"{location}.turns[{turn_index}]"
            if not isinstance(turn, dict):
                errors.append(f"{turn_location}: expected an object")
                continue

            outcome = turn.get("expect")
            fields = {"user", "expect"}
            if outcome == "offer_journey":
                fields.add("workflow_id")
            if set(turn) != fields:
                errors.append(f"{turn_location}: expected fields {sorted(fields)}")
            if not isinstance(turn.get("user"), str) or not turn["user"].strip():
                errors.append(f"{turn_location}: user must be a non-empty string")
            if outcome not in OUTCOMES:
                errors.append(f"{turn_location}: unknown outcome {outcome!r}")
            if outcome == "offer_journey":
                if turn.get("workflow_id") not in workflow_ids:
                    errors.append(f"{turn_location}: unknown workflow_id {turn.get('workflow_id')!r}")
            if turn_index < len(turns) - 1 and outcome != "clarify":
                errors.append(f"{turn_location}: intermediate turn must clarify")
            if turn_index == len(turns) - 1 and outcome == "clarify":
                errors.append(f"{turn_location}: final turn cannot clarify")
            if scenario["search"] == "forbidden" and outcome == "offer_journey":
                errors.append(f"{turn_location}: forbidden-search scenario cannot offer a journey")

    if errors:
        raise SystemExit("\n".join(errors))

    categories = Counter(scenario["category"] for scenario in scenarios)
    print(f"PASS: {len(scenarios)} scenarios; {sum(len(s['turns']) for s in scenarios)} turns")
    print(f"Categories: {dict(categories)}")
    print(f"All offered workflow IDs found in {CATALOGUE_PATH}")


if __name__ == "__main__":
    validate()
