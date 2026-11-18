"""Record agent runs at the Journey Search contract boundary and build the demo page.

Runs a stand-in orchestrator (a Strands agent on Claude via Bedrock) with the
``search_service_journeys`` tool over a few scenarios, and records only what
crosses the boundary defined in the Journey Search Contract RFC: the
citizen's messages, each search request and response exactly as exchanged,
and the orchestrator's replies. How search works inside is deliberately left
out, because it is not part of the contract.

The recording is inlined into a single HTML page styled with GOV.UK Frontend,
so the demo can be shown without AWS access.

Usage (from the repository root, with AWS credentials):

    uv run python -m forms_search.demo.record_demo            # record and build
    uv run python -m forms_search.demo.record_demo --only badge   # record one scenario
    uv run python -m forms_search.demo.record_demo --build    # rebuild from demo_data.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent.parent
DATA_PATH = DEMO_DIR / "demo_data.json"
TEMPLATE_PATH = DEMO_DIR / "template.html"
OUTPUT_PATH = DEMO_DIR / "index.html"
# Body-only copy for publishing as a hosted page, which supplies its own skeleton.
FRAGMENT_PATH = DEMO_DIR / "build" / "journey-search-demo.html"
GOVUK_CSS = (
    REPO_ROOT
    / "forms_frontend/frontend/node_modules/govuk-frontend/dist/govuk/govuk-frontend.min.css"
)

ORCHESTRATOR_MODEL = "eu.anthropic.claude-sonnet-5-5"

# A stand-in for the GOV.UK orchestrator, which another team owns. It follows the
# orchestrator responsibilities in section 4 of the RFC.
SYSTEM_PROMPT = (
    "You are the GOV.UK assistant. You help citizens use government services. Keep replies short.\n"
    "You do not know in advance which service journeys exist. Search for them when the citizen may want "
    "to do something a government service could handle. Do not search for general information questions.\n"
    "Search results are candidates, not matches. Judge each one yourself, even if only one is returned. Then:\n"
    "- if one journey fits, name it and offer to start it, but do not start it until the citizen agrees;\n"
    "- if several could fit, or you need more information, ask the citizen or let them choose;\n"
    "- if none fits, say you have not found a suitable service.\n"
    "If the citizen's answer settles which journey they need, choose from the candidates you already have "
    "rather than searching again."
)

# Each scenario is one or more citizen turns. "decisions" labels each reply with the
# RFC outcome it represents; the labels are checked against the replies after recording.
# Order, labels and explanations are applied at build time, so editing them only needs --build.
SCENARIOS = [
    {
        "id": "badge",
        "label": "Standard request",
        "turns": ["I've lost my armed forces veterans badge. How do I get a new one?"],
        "decisions": ["execute"],
        "point": "A routine request. The orchestrator searches, and one candidate clearly fits.",
        "response_notes": [
            "The orchestrator judges that the first candidate, “Apply for or replace an armed forces veterans "
            "badge”, fits. The other four are feedback and technical-issue forms for related services, so it "
            "sets them aside."
        ],
    },
    {
        "id": "octopus",
        "label": "Unexpected service",
        "turns": ["I was diving near Plymouth yesterday and spotted an octopus!"],
        "decisions": ["execute"],
        "point": "The citizen describes something they saw, without asking for a service. The "
        "orchestrator judges that a government service might handle it, so it searches rather than "
        "assuming no such journey exists.",
        "response_notes": [
            "The orchestrator judges that the first candidate, “Octopus sighting? Let us know!”, fits. The other "
            "four are unrelated. That is expected: search returns up to the limit even when only one candidate "
            "is relevant."
        ],
    },
    {
        "id": "clarify",
        "label": "Ambiguous need",
        "turns": [
            "I need to change something on my redundancy claim.",
            "It's holiday I took but was never paid for.",
        ],
        "decisions": ["clarify", "execute"],
        "point": "Several journeys could fit. The orchestrator asks the citizen, then chooses from the "
        "candidates it already has.",
        "response_notes": [
            "All five candidates amend a redundancy claim, and the citizen's message does not say which part "
            "needs changing. The orchestrator cannot tell which fits, so it asks. It keeps these candidates "
            "for the next turn."
        ],
    },
    {
        "id": "cartel",
        "label": "No obvious keywords",
        "turns": [
            "I run a small building firm and I think our timber suppliers are secretly agreeing prices."
        ],
        "decisions": ["execute"],
        "point": "The citizen's words do not match the journey's title. The orchestrator writes a "
        "self-contained query describing the need, and search finds the right journey.",
        "response_notes": [
            "The orchestrator judges that the first candidate, “Report a cartel to the CMA”, fits. Candidates "
            "2 to 4 are about reporting sanctions breaches, which is a different need."
        ],
    },
    {
        "id": "passport",
        "label": "Not in the catalogue",
        "turns": ["I need to renew my passport."],
        "decisions": ["do_not_route"],
        "point": "Search returns candidates even when none is right. The orchestrator must judge them, "
        "and here it finds none suitable. What it does next is outside this contract.",
        "response_notes": [
            "None of these is about a travel passport. The top candidate is about plant passports. The "
            "orchestrator judges none suitable and searches again.",
            "Still no passport renewal. The closest is “Apply for an emergency travel document (first time "
            "applicant)”, which does not fit a renewal, so the orchestrator rejects it too.",
        ],
    },
    {
        "id": "travel",
        "label": "Information question",
        "turns": ["What's the FCDO travel advice for Spain?"],
        "decisions": ["no_search"],
        "point": "Deciding when to search belongs to the orchestrator. This is a question rather than "
        "something a service journey does, so it does not search Legibility.",
    },
]

PRESENTATION_FIELDS = ("label", "point", "response_notes")


def boundary_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Search requests and responses, in order, from new agent messages."""
    events = []
    for message in messages:
        for block in message.get("content", []):
            use = block.get("toolUse")
            if use and use["name"] == "search_service_journeys":
                events.append({"kind": "search_request", "input": use["input"]})
            result = block.get("toolResult")
            if result:
                events.append(
                    {
                        "kind": "search_response",
                        "status": result["status"],
                        "json": result["content"][0].get("json"),
                    }
                )
    return events


def record(only: set[str] | None) -> dict[str, Any]:
    """Record the selected scenarios (all if ``only`` is None), keeping earlier recordings of the rest."""
    from strands import Agent
    from strands.models import BedrockModel

    from forms_search import tool

    data = (
        json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if only and DATA_PATH.exists()
        else {}
    )
    recorded = {s["id"]: s for s in data.get("scenarios", [])}
    today = datetime.now(UTC).strftime("%-d %B %Y")
    index = tool.get_index()

    for scenario in SCENARIOS:
        if only and scenario["id"] not in only:
            continue
        agent = Agent(
            model=BedrockModel(model_id=ORCHESTRATOR_MODEL, region_name="eu-west-2"),
            tools=[tool.search_service_journeys],
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
        )
        events: list[dict[str, Any]] = []
        for turn, decision in zip(scenario["turns"], scenario["decisions"]):
            before = len(agent.messages)
            events.append({"kind": "citizen", "text": turn})
            result = agent(turn)
            events.extend(boundary_events(agent.messages[before:]))
            events.append(
                {"kind": "reply", "text": str(result).strip(), "decision": decision}
            )
        recorded[scenario["id"]] = {
            "id": scenario["id"],
            "recorded_at": today,
            "events": events,
        }
        searches = sum(e["kind"] == "search_request" for e in events)
        print(f"recorded {scenario['id']}: {searches} searches")
        for e in events:
            if e["kind"] == "reply":
                print(f"   [{e['decision']}] {e['text'][:200]!r}")

    return {
        "recorded_at": today,
        "orchestrator_model": ORCHESTRATOR_MODEL,
        "catalogue_size": len(index.journeys),
        "system_prompt": SYSTEM_PROMPT,
        "scenarios": list(recorded.values()),
    }


def for_page(data: dict[str, Any]) -> dict[str, Any]:
    """Recorded events in SCENARIOS order, with each scenario's current label and explanation."""
    recorded = {s["id"]: s for s in data["scenarios"]}
    missing = [s["id"] for s in SCENARIOS if s["id"] not in recorded]
    if missing:
        raise SystemExit(
            f"not recorded yet: {', '.join(missing)} (use --only {' '.join(missing)})"
        )
    scenarios = [
        {
            "id": s["id"],
            **{k: s.get(k) for k in PRESENTATION_FIELDS},
            "events": recorded[s["id"]]["events"],
        }
        for s in SCENARIOS
    ]
    return {**data, "scenarios": scenarios}


def govuk_css() -> str:
    """GOV.UK Frontend's stylesheet, without the font and image files the page cannot load."""
    if not GOVUK_CSS.exists():
        raise SystemExit(
            f"GOV.UK Frontend not found at {GOVUK_CSS}; run npm install in forms_frontend/frontend"
        )
    css = GOVUK_CSS.read_text(encoding="utf-8").removeprefix('@charset "UTF-8";')
    css = re.sub(r"@font-face\{[^}]*\}", "", css)
    return re.sub(r"url\(/assets/images/[^)]*\)", "none", css)


def build(data: dict[str, Any]) -> None:
    # Escape "</" so recorded text can never close the inline <script>.
    payload = json.dumps(for_page(data), ensure_ascii=False).replace("</", "<\\/")
    fragment = (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("/*__GOVUK_FRONTEND_CSS__*/", govuk_css())
        .replace("/*__DEMO_DATA__*/null", payload)
    )
    FRAGMENT_PATH.parent.mkdir(exist_ok=True)
    FRAGMENT_PATH.write_text(fragment, encoding="utf-8")
    OUTPUT_PATH.write_text(
        '<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "</head>\n<body>\n" + fragment + "\n</body>\n</html>\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--build", action="store_true", help="Rebuild the page from demo_data.json only"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="Record only these scenarios, keeping the others",
    )
    args = parser.parse_args()
    if args.build:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    else:
        data = record(set(args.only) if args.only else None)
        DATA_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    build(data)


if __name__ == "__main__":
    main()
