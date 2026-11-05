"""Build the Journey Search handover deck from the dataset and saved reference-run traces.

Reads (never writes) `forms_search/evals/scenarios.json`, `evals/results/full/` and
`evals/results/fixes/`, and writes `index.html` (and `demo_data.json`, for inspection) in this
directory. Makes no Bedrock or MCP calls.

    uv run python forms_search/demo_evals/build.py   # from the repository root
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent / "evals"
RESULTS = EVALS / "results"
TOOL_NAME = "search_service_journeys"
DECISION_TOOL = "TurnDecision"

# Scenarios shown as JSON on the "what a scenario looks like" slide.
SCENARIO_SAMPLES = ["catalogue_1994", "cancelled_test_theory"]

# The recorded response shown on the tool slide (first candidates only).
TOOL_SAMPLE = ("catalogue_1994", 2)

# Traces in the example explorer. `label` and `point` are our framing; the rest is recorded.
EXAMPLES = [
    {"id": "unusual_octopus", "label": "Unexpected service",
     "point": "The agent doesn't know the catalogue, but searches anyway and finds a niche Form."},
    {"id": "cancelled_test_theory", "label": "Clarification",
     "point": "Two Forms fit, so it asks. The scripted second message is sent verbatim."},
    {"id": "similar_holiday_taken", "label": "Similar Forms",
     "point": "Near-identical redundancy-claim Forms. The request is specific enough to pick one."},
    {"id": "outside_passport_renewal", "label": "Nothing fits",
     "point": "Search always returns candidates. The agent searches twice, then rejects them all."},
    {"id": "no_search_greeting", "label": "No search",
     "point": "Small talk: Journey Search is never called."},
]


def load_jsonl(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f) if r.get("id")}


# --- Scoring: the same rules as evals/run_evals.py (score_turn and score) --------------------


def score_turn(expected: dict, observed: dict) -> bool:
    offered = observed["workflow_ids"]
    if expected["expect"] == "offer_journey":
        return observed["outcome"] == "offer_journey" and offered == [expected["workflow_id"]]
    if expected["expect"] == "clarify":
        return observed["outcome"] == "clarify"
    return observed["outcome"] != "offer_journey" and not offered


def passed(scenario: dict, record: dict) -> bool:
    if record.get("error"):
        return False
    turns = record["turns"]
    searches = sum(len(t["searches"]) for t in turns)
    search_ok = searches > 0 if scenario["search"] == "required" else searches == 0
    return (
        search_ok
        and len(turns) == len(scenario["turns"])
        and all(score_turn(e, o) for e, o in zip(scenario["turns"], turns))
    )


# --- Traces ----------------------------------------------------------------------------------


def tool_payload(block: dict) -> object:
    for item in block.get("content", []):
        if "json" in item:
            return item["json"]
        if "text" in item:
            try:
                return json.loads(item["text"])
            except json.JSONDecodeError:
                return item["text"]
    return None


def events_from(messages: list[dict]) -> list[dict]:
    """Citizen messages, Journey Search calls and results, and decisions, in recorded order."""
    events, searches = [], set()
    for message in messages:
        for block in message["content"]:
            if message["role"] == "user" and "text" in block:
                events.append({"kind": "citizen", "text": block["text"]})
            elif "toolUse" in block and block["toolUse"]["name"] == TOOL_NAME:
                searches.add(block["toolUse"]["toolUseId"])
                events.append({"kind": "search", "input": block["toolUse"]["input"]})
            elif "toolResult" in block and block["toolResult"]["toolUseId"] in searches:
                events.append({"kind": "result", "json": tool_payload(block["toolResult"])})
            elif "toolUse" in block and block["toolUse"]["name"] == DECISION_TOOL:
                d = block["toolUse"]["input"]
                events.append({
                    "kind": "decision",
                    "outcome": d.get("outcome"),
                    "workflow_ids": [str(w) for w in d.get("workflow_ids", [])],
                    "reply": d.get("reply", ""),
                })
    return events


def main() -> None:
    data = json.loads((EVALS / "scenarios.json").read_text(encoding="utf-8"))
    current = {s["id"]: s for s in (data["scenarios"] if isinstance(data, dict) else data)}
    full = load_jsonl(RESULTS / "full" / "results.jsonl")
    fixes = load_jsonl(RESULTS / "fixes" / "results.jsonl")
    # Rewritten scenarios were rerun in `fixes`; everything else is from the full run.
    latest = {sid: fixes.get(sid) or full[sid] for sid in current}

    examples = []
    for ex in EXAMPLES:
        scenario, record = current[ex["id"]], latest[ex["id"]]
        events = events_from(record["messages"])
        # The recorded citizen turns must be the current dataset's wording.
        assert [e["text"] for e in events if e["kind"] == "citizen"] == [t["user"] for t in scenario["turns"]]
        examples.append({**ex, "scenario": scenario, "passed": passed(scenario, record), "events": events})

    sample_id, n = TOOL_SAMPLE
    sample_events = events_from(latest[sample_id]["messages"])
    query = next(e for e in sample_events if e["kind"] == "search")["input"]
    response = next(e for e in sample_events if e["kind"] == "result")["json"]

    run = json.loads((RESULTS / "full" / "run.json").read_text(encoding="utf-8"))
    demo = {
        "dataset": {
            "total": len(current),
            "by_category": dict(Counter(s["category"] for s in current.values()).most_common()),
            "by_turns": dict(sorted(Counter(len(s["turns"]) for s in current.values()).items())),
        },
        "reference": {
            "passed": sum(passed(current[sid], latest[sid]) for sid in current),
            "total": len(current),
            "model_id": run["model_id"],
        },
        "tool_sample": {"input": query, "candidates": response["candidates"][:n],
                        "of": len(response["candidates"])},
        "scenario_samples": [current[sid] for sid in SCENARIO_SAMPLES],
        "examples": examples,
    }
    (HERE / "demo_data.json").write_text(json.dumps(demo, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    page_data = json.dumps(demo, ensure_ascii=False).replace("</", "<\\/")
    html = (HERE / "template.html").read_text(encoding="utf-8").replace("/*__DEMO_DATA__*/null", page_data)
    (HERE / "index.html").write_text(html, encoding="utf-8")
    r = demo["reference"]
    print(f"Scenarios {demo['dataset']['total']}; reference agent {r['passed']}/{r['total']}")
    print(f"Wrote {HERE / 'index.html'} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
