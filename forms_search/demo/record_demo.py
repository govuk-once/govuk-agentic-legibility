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
    "- if one journey fits, name it and offer to start it;\n"
    "- if several could fit, or you need more information, ask the citizen or let them choose;\n"
    "- if none fits, say you have not found a suitable service.\n"
    "If the citizen's answer settles which journey they need, choose from the candidates you already have "
    "rather than searching again. You cannot start journeys in this demo."
)

# Each scenario is one or more citizen turns. "decisions" labels each reply with the
# RFC outcome it represents; the labels are checked against the replies after recording.
SCENARIOS = [
    {
        "id": "octopus",
        "label": "Unexpected service",
        "turns": ["I was diving near Plymouth yesterday and spotted an octopus!"],
        "decisions": ["execute"],
        "point": "The citizen does not ask for a service, and nobody would expect one to exist. The "
        "orchestrator searches anyway, because it should not assume it knows which journeys exist.",
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
    },
    {
        "id": "passport",
        "label": "Not in the catalogue",
        "turns": ["I need to renew my passport."],
        "decisions": ["do_not_route"],
        "point": "Search returns candidates even when none is right. The orchestrator must judge them, "
        "and here it finds none suitable.",
    },
    {
        "id": "travel",
        "label": "Information question",
        "turns": ["What's the FCDO travel advice for Spain?"],
        "decisions": ["no_search"],
        "point": "Deciding when to search belongs to the orchestrator. This is a question, not something "
        "a service journey does, so it answers without searching.",
    },
]


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


def record() -> dict[str, Any]:
    from strands import Agent
    from strands.models import BedrockModel

    from forms_search import tool

    index = tool.get_index()
    runs = []
    for scenario in SCENARIOS:
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
        kept = {k: v for k, v in scenario.items() if k not in ("turns", "decisions")}
        runs.append(kept | {"events": events})
        searches = sum(e["kind"] == "search_request" for e in events)
        print(f"recorded {scenario['id']}: {searches} searches")
        for e in events:
            if e["kind"] == "reply":
                print(f"   [{e['decision']}] {e['text'][:200]!r}")

    return {
        "recorded_at": datetime.now(UTC).strftime("%-d %B %Y"),
        "orchestrator_model": ORCHESTRATOR_MODEL,
        "catalogue_size": len(index.journeys),
        "system_prompt": SYSTEM_PROMPT,
        "scenarios": runs,
    }


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
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    fragment = (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("/*__GOVUK_FRONTEND_CSS__*/", govuk_css())
        .replace("/*__DEMO_DATA__*/null", payload)
    )
    FRAGMENT_PATH.parent.mkdir(exist_ok=True)
    FRAGMENT_PATH.write_text(fragment, encoding="utf-8")
    OUTPUT_PATH.write_text(
        '<!doctype html>\n<html lang="en-GB" class="govuk-template">\n<head>\n<meta charset="utf-8">\n'
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
    args = parser.parse_args()
    if args.build:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    else:
        data = record()
        DATA_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    build(data)


if __name__ == "__main__":
    main()
