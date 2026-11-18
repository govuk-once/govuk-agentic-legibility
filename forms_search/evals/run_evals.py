# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "strands-agents>=1.53",
#     "truststore>=0.10",
#     "boto3",
# ]
# ///
"""Run the evaluation scenarios against a local reference Strands agent.

The agent uses the real, deployed Journey Search MCP tool. This is for
sense-checking the dataset, not for assessing the GOV.UK orchestrator.
See RUNNER_NOTES.md for the design and scoring rules.

From the repository root:

    uv run forms_search/evals/run_evals.py run --run smoke --ids unusual_octopus cancelled_test_theory
    uv run forms_search/evals/run_evals.py run --run sample --per-category 5
    uv run forms_search/evals/run_evals.py run --run full --concurrency 6
    uv run forms_search/evals/run_evals.py report --run full

Re-running `run` with the same --run name resumes: scenarios already completed
without an error are skipped. Results are written to evals/results/<run>/.

Journey Search settings come from the JOURNEY_SEARCH_* environment variables
(see journey_search/CONNECTING.md). If they are not set, they are read from the
JourneySearchStack outputs and its Cognito client using your AWS credentials,
in memory only.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
from typing import Literal

EVALS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS_DIR.parent / "journey_search" / "examples"))

import strands_client  # noqa: E402  (also injects truststore and quietens MCP logging)

from botocore.config import Config  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

SCENARIOS_PATH = EVALS_DIR / "scenarios.json"
CATALOGUE_PATH = EVALS_DIR.parent / "data" / "catalogue.json"
RESULTS_DIR = EVALS_DIR / "results"
TOOL_NAME = strands_client.TOOL_NAME
STACK_NAME = "JourneySearchStack"
STACK_REGION = "eu-west-2"

SYSTEM_PROMPT = """\
You are a GOV.UK assistant helping members of the public with UK government services.

You can search a catalogue of GOV.UK service journeys (online forms) with the \
search_service_journeys tool. You can't start a journey in this conversation: when one fits, \
offer it and the citizen decides whether to start it.

- Search when the citizen may want to do something a government service journey could handle, \
including unusual or specialised things. You don't need to search for general information \
questions or small talk.
- Search results are only candidates. Judge whether each one really fits what the citizen wants. \
You can search again with a better query.
- If one journey fits, offer it. If more than one could fit and you can't tell which the citizen \
needs, ask them. If none fits, say so and help as best you can without one.

Keep replies short and plain."""


class TurnDecision(BaseModel):
    """Your reply to the citizen for this turn, and what kind of reply it is."""

    reply: str = Field(description="The message to the citizen, exactly as they will see it.")
    outcome: Literal["offer_journey", "clarify", "no_journey"] = Field(
        description=(
            "offer_journey: you are proposing one specific service journey for the citizen to start. "
            "clarify: you are asking the citizen a question, or to choose between options, before "
            "you can propose a journey. "
            "no_journey: you are not proposing a journey, for example because you answered a "
            "question or found nothing suitable."
        )
    )
    workflow_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The workflow_id of every journey your reply proposes or presents as an option. "
            "Empty if your reply mentions no journey."
        ),
    )


# --- Connecting ------------------------------------------------------------------------------


def ensure_journey_search_settings() -> str:
    """Fill in JOURNEY_SEARCH_* from the deployed stack if they aren't already set."""
    if all(os.environ.get(name) for name in strands_client.SETTINGS):
        return "environment"
    import boto3

    stack = boto3.client("cloudformation", region_name=STACK_REGION).describe_stacks(
        StackName=STACK_NAME
    )["Stacks"][0]
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    secret = boto3.client("cognito-idp", region_name=STACK_REGION).describe_user_pool_client(
        UserPoolId=outputs["UserPoolId"], ClientId=outputs["ClientId"]
    )["UserPoolClient"]["ClientSecret"]
    os.environ.setdefault("JOURNEY_SEARCH_MCP_URL", outputs["McpUrl"])
    os.environ.setdefault("JOURNEY_SEARCH_TOKEN_URL", outputs["TokenUrl"])
    os.environ.setdefault("JOURNEY_SEARCH_CLIENT_ID", outputs["ClientId"])
    os.environ.setdefault("JOURNEY_SEARCH_SCOPE", outputs["Scope"])
    os.environ.setdefault("JOURNEY_SEARCH_CLIENT_SECRET", secret)
    return f"{STACK_NAME} outputs"


# --- Running a scenario ----------------------------------------------------------------------


def tool_result_payload(block: dict) -> object:
    for item in block.get("content", []):
        if "json" in item:
            return item["json"]
        if "text" in item:
            try:
                return json.loads(item["text"])
            except json.JSONDecodeError:
                return item["text"]
    return None


def searches_in(messages: list[dict]) -> list[dict]:
    """The Journey Search calls, with their queries and returned candidates, in order."""
    calls, by_id = [], {}
    for message in messages:
        for block in message["content"]:
            if "toolUse" in block and block["toolUse"]["name"] == TOOL_NAME:
                call = {"input": block["toolUse"]["input"], "status": None, "candidates": None}
                by_id[block["toolUse"]["toolUseId"]] = call
                calls.append(call)
            elif "toolResult" in block and block["toolResult"]["toolUseId"] in by_id:
                call = by_id[block["toolResult"]["toolUseId"]]
                payload = tool_result_payload(block["toolResult"])
                call["status"] = block["toolResult"].get("status")
                if isinstance(payload, dict) and "candidates" in payload:
                    call["candidates"] = [
                        {"workflow_id": c["workflow_id"], "title": c["title"]}
                        for c in payload["candidates"]
                    ]
                else:
                    call["error"] = payload
    return calls


def run_scenario(scenario: dict, model, tools: list) -> dict:
    from strands import Agent

    agent = Agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT, callback_handler=None)
    observed, started = [], time.monotonic()
    for turn in scenario["turns"]:
        first_message = len(agent.messages)
        result = agent(turn["user"], structured_output_model=TurnDecision)
        decision: TurnDecision = result.structured_output
        observed.append(
            {
                "user": turn["user"],
                "searches": searches_in(agent.messages[first_message:]),
                "outcome": decision.outcome,
                "workflow_ids": [str(w) for w in decision.workflow_ids],
                "reply": decision.reply,
            }
        )
        if not score_turn(turn, observed[-1])["passed"]:
            break  # a failed intermediate turn ends the scenario
    usage = agent.event_loop_metrics.accumulated_usage
    return {
        "turns": observed,
        "seconds": round(time.monotonic() - started, 1),
        "usage": {k: usage.get(k, 0) for k in ("inputTokens", "outputTokens", "totalTokens")},
        "messages": agent.messages,
    }


# --- Scoring ---------------------------------------------------------------------------------


def score_turn(expected: dict, observed: dict) -> dict:
    offered = observed["workflow_ids"]
    if expected["expect"] == "offer_journey":
        passed = observed["outcome"] == "offer_journey" and offered == [expected["workflow_id"]]
    elif expected["expect"] == "clarify":
        passed = observed["outcome"] == "clarify"
    else:
        passed = observed["outcome"] != "offer_journey" and not offered
    return {"passed": passed}


def score(scenario: dict, record: dict) -> dict:
    """Deterministic score for one scenario from its recorded observations."""
    if record.get("error"):
        return {"passed": False, "error": True}
    turns = record["turns"]
    search_count = sum(len(t["searches"]) for t in turns)
    search_ok = search_count > 0 if scenario["search"] == "required" else search_count == 0
    turn_scores = [score_turn(e, o)["passed"] for e, o in zip(scenario["turns"], turns)]
    completed = len(turns) == len(scenario["turns"])
    final = scenario["turns"][-1]
    expected_id = final.get("workflow_id")
    retrieved = {
        c["workflow_id"]
        for t in turns
        for s in t["searches"]
        for c in (s["candidates"] or [])
    }
    wrong_offers = sorted({w for t in turns for w in t["workflow_ids"] if w != expected_id})
    return {
        "passed": search_ok and completed and all(turn_scores),
        "search_ok": search_ok,
        "search_count": search_count,
        "turns_passed": turn_scores,
        "completed": completed,
        "expected_retrieved": expected_id in retrieved if expected_id else None,
        "wrong_offers": wrong_offers,
        "error": False,
    }


# --- Commands --------------------------------------------------------------------------------


def load_results(path: Path) -> dict[str, dict]:
    results = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                results[record["id"]] = record  # later lines replace earlier attempts
    return results


def select(scenarios: list[dict], args) -> list[dict]:
    chosen = scenarios
    if args.ids:
        wanted = set(args.ids)
        chosen = [s for s in chosen if s["id"] in wanted]
        missing = wanted - {s["id"] for s in chosen}
        if missing:
            sys.exit(f"Unknown scenario IDs: {', '.join(sorted(missing))}")
    if args.category:
        chosen = [s for s in chosen if s["category"] in set(args.category)]
    if args.per_category:
        rng, by_category = random.Random(args.seed), defaultdict(list)
        for s in chosen:
            by_category[s["category"]].append(s)
        picked = set()
        for group in by_category.values():
            picked |= {s["id"] for s in rng.sample(group, min(args.per_category, len(group)))}
        chosen = [s for s in chosen if s["id"] in picked]
    if args.limit:
        chosen = chosen[: args.limit]
    return chosen


def run(args) -> None:
    from strands.models import BedrockModel

    scenarios = select(json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"], args)
    run_dir = RESULTS_DIR / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    done = {i for i, r in load_results(results_path).items() if not r.get("error")}
    todo = [s for s in scenarios if s["id"] not in done]
    print(f"{len(scenarios)} selected, {len(scenarios) - len(todo)} already done, {len(todo)} to run")
    if not todo:
        return

    print(f"Journey Search settings from {ensure_journey_search_settings()}")
    client = strands_client.journey_search_client(None)
    client.start()
    try:
        tools = client.list_tools_sync()
        spec = next(t.tool_spec for t in tools if t.tool_spec["name"] == TOOL_NAME)
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "model_id": args.model_id,
                    "region": args.region,
                    "system_prompt": SYSTEM_PROMPT,
                    "decision_schema": TurnDecision.model_json_schema(),
                    "tool_spec": spec,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        model = BedrockModel(
            model_id=args.model_id,
            region_name=args.region,
            boto_client_config=Config(retries={"max_attempts": 10, "mode": "adaptive"}, read_timeout=300),
        )
        lock, passed, finished = threading.Lock(), 0, 0

        def attempt(scenario: dict) -> dict:
            record = {"id": scenario["id"], "category": scenario["category"], "model_id": args.model_id}
            try:
                record |= run_scenario(scenario, model, tools)
            except Exception as exc:  # recorded and retried on the next resume
                record["error"] = f"{type(exc).__name__}: {exc}"
            return record

        with results_path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(args.concurrency) as pool:
            futures = {pool.submit(attempt, s): s for s in todo}
            for future in as_completed(futures):
                scenario, record = futures[future], future.result()
                result = score(scenario, record)
                with lock:
                    out.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    out.flush()
                    finished += 1
                    passed += result["passed"]
                status = "ERROR " + record["error"][:80] if record.get("error") else (
                    "pass" if result["passed"] else "FAIL"
                )
                print(f"[{finished}/{len(todo)}] {scenario['id']}: {status}", flush=True)
        print(f"{passed}/{len(todo)} passed in this session")
    finally:
        client.stop(None, None, None)
    report(args)


def report(args) -> None:
    run_dir = RESULTS_DIR / args.run
    scenarios = {s["id"]: s for s in json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]}
    titles = {
        w["workflow_id"]: w["title"]
        for w in json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))["workflows"]
    }
    results = load_results(run_dir / "results.jsonl")
    rows = [(scenarios[i], r, score(scenarios[i], r)) for i, r in results.items() if i in scenarios]
    rows.sort(key=lambda row: list(scenarios).index(row[0]["id"]))

    def pct(n: int, d: int) -> str:
        return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "–"

    def label(workflow_id: str | None) -> str:
        return f"`{workflow_id}` {titles.get(workflow_id, '?')}" if workflow_id else "–"

    lines = [f"# Reference agent run: `{args.run}`", ""]
    scored = [row for row in rows if not row[2]["error"]]
    errors = [row for row in rows if row[2]["error"]]
    lines += [
        f"- Scenarios recorded: {len(rows)} ({len(errors)} errored)",
        f"- **Passed: {pct(sum(r[2]['passed'] for r in scored), len(scored))}** of scored scenarios",
        f"- Model: `{next(iter(results.values()), {}).get('model_id', '?')}`",
        "",
        "## By category",
        "",
        "| Category | Passed | Search behaviour OK | Expected ID retrieved | Mean searches |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    by_category = defaultdict(list)
    for row in scored:
        by_category[row[0]["category"]].append(row)
    for category, group in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        with_id = [g for g in group if g[2]["expected_retrieved"] is not None]
        lines.append(
            f"| {category} | {pct(sum(g[2]['passed'] for g in group), len(group))} "
            f"| {pct(sum(g[2]['search_ok'] for g in group), len(group))} "
            f"| {pct(sum(g[2]['expected_retrieved'] for g in with_id), len(with_id))} "
            f"| {sum(g[2]['search_count'] for g in group) / len(group):.1f} |"
        )

    offer_rows = [r for r in scored if r[0]["turns"][-1]["expect"] == "offer_journey"]
    clarify_rows = [r for r in scored if r[0]["turns"][0]["expect"] == "clarify"]
    outcomes = Counter(r[1]["turns"][-1]["outcome"] for r in offer_rows if r[2]["completed"])
    lines += [
        "",
        "## Headline checks",
        "",
        f"- Search when required: {pct(sum(r[2]['search_ok'] for r in scored if r[0]['search'] == 'required'), sum(r[0]['search'] == 'required' for r in scored))}",
        f"- No search when forbidden: {pct(sum(r[2]['search_ok'] for r in scored if r[0]['search'] == 'forbidden'), sum(r[0]['search'] == 'forbidden' for r in scored))}",
        f"- Correct journey offered (all offer_journey scenarios): {pct(sum(r[2]['passed'] for r in offer_rows), len(offer_rows))}",
        f"  - final-turn outcomes: {dict(outcomes)}",
        f"- Clarification asked on turn 1: {pct(sum(r[2]['turns_passed'][0] for r in clarify_rows), len(clarify_rows))}; "
        f"then correct journey: {pct(sum(r[2]['passed'] for r in clarify_rows), len(clarify_rows))}",
        f"- Scenarios where a journey other than the expected one was offered: "
        f"{sum(bool(r[2]['wrong_offers']) for r in scored)}",
        f"- Tokens: {sum(r[1]['usage']['totalTokens'] for r in scored):,} total",
        "",
        "## Failures",
        "",
    ]
    for scenario, record, result in scored:
        if result["passed"]:
            continue
        expected = scenario["turns"][-1]
        if not result["search_ok"]:
            kind = "searched when forbidden" if scenario["search"] == "forbidden" else "did not search"
        elif result["expected_retrieved"] is False:
            kind = "expected journey never retrieved"
        elif not result["completed"]:
            kind = "did not clarify on turn 1"
        else:
            kind = "wrong decision"
        lines.append(f"### `{scenario['id']}` ({scenario['category']}): {kind}")
        lines.append("")
        lines.append(f"- Expected: {expected['expect']} {label(expected.get('workflow_id'))}")
        for number, turn in enumerate(record["turns"], 1):
            lines.append(f"- Turn {number} citizen: {turn['user']}")
            for search in turn["searches"]:
                found = ", ".join(c["workflow_id"] for c in search["candidates"] or []) or search.get("error")
                lines.append(f"  - search `{search['input'].get('query')}` → {found}")
            offered = "; ".join(label(w) for w in turn["workflow_ids"]) or "none"
            lines.append(f"  - agent: **{turn['outcome']}** — {offered}")
            lines.append(f"  - reply: {turn['reply'][:400].replace(chr(10), ' ')}")
        lines.append("")
    if errors:
        lines += ["## Errors", ""] + [f"- `{r[0]['id']}`: {r[1]['error'][:200]}" for r in errors]

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {run_dir / 'summary.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Run scenarios, then write the summary")
    report_parser = commands.add_parser("report", help="Rewrite the summary from saved results")
    for p in (run_parser, report_parser):
        p.add_argument("--run", required=True, help="Run name; results go in evals/results/<run>/")
    run_parser.add_argument("--ids", nargs="+", help="Only these scenario IDs")
    run_parser.add_argument("--category", nargs="+", help="Only these categories")
    run_parser.add_argument("--per-category", type=int, help="Random sample of N per category")
    run_parser.add_argument("--seed", type=int, default=1)
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--concurrency", type=int, default=4)
    run_parser.add_argument("--model-id", default="eu.anthropic.claude-sonnet-5-5")
    run_parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-west-2"))
    args = parser.parse_args()
    run(args) if args.command == "run" else report(args)


if __name__ == "__main__":
    main()
