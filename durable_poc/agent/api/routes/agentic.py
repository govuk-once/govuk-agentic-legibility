"""Autonomous run control for `/agentic`: `AutonomyPolicy` + the
`escalate_to_human`-driven resume loop.

This is the one route besides `chat_ws`/`voice_ws` that imports
`agent.agent.WorkflowAgent` — see `ARCHITECTURE.md`'s Dual-Path principle.
Every autonomous `submit_input` decision is tagged with its provenance and
streamed as a `RunEvent`, the same vocabulary `GET /runs/{id}/events` uses, so
the exception to "the agent never decides a value" is auditable rather than
silent.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent import tools as tool_functions
from agent.api import deps
from agent.api.events import RunEvent
from agent.api.schemas import SetAutonomyRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agentic"])

EVALUATION_SCENARIOS_ROOT = (
    Path(__file__).resolve().parents[3] / "evaluation" / "scenarios"
)
MAX_AUTONOMOUS_STEPS = 25

# In-memory, process-wide autonomy config per run. No auth or persistence yet
# (flagged as out of scope in the plan) — this is local-demo-only state.
_autonomy_config: dict[str, SetAutonomyRequest] = {}


def _load_profile_conversation(profile_fixture: str) -> list[dict[str, Any]]:
    """Load a `conversation.json` fixture's turns as Strands-format history."""
    fixture_dir = (EVALUATION_SCENARIOS_ROOT / profile_fixture).resolve()
    if fixture_dir != EVALUATION_SCENARIOS_ROOT and EVALUATION_SCENARIOS_ROOT not in fixture_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid profile_fixture path")

    conversation_path = fixture_dir / "conversation.json"
    if not conversation_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No conversation.json for {profile_fixture!r}"
        )

    data = json.loads(conversation_path.read_text(encoding="utf-8"))
    turns = data.get("conversation", [])
    return [
        {"role": turn["role"], "content": [{"text": turn["content"]}]}
        for turn in turns
        if turn.get("role") in ("user", "assistant")
    ]


@router.get("/profiles")
async def list_profiles() -> list[dict[str, str]]:
    """List evaluation-scenario fixtures usable as `/agentic` profile bundles."""
    if not EVALUATION_SCENARIOS_ROOT.exists():
        return []
    profiles = []
    for conversation_path in sorted(EVALUATION_SCENARIOS_ROOT.glob("*/*/conversation.json")):
        fixture = str(conversation_path.parent.relative_to(EVALUATION_SCENARIOS_ROOT))
        try:
            data = json.loads(conversation_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        profiles.append(
            {
                "fixture": fixture,
                "title": data.get("title", fixture),
                "journey_id": data.get("journey_id", ""),
            }
        )
    return profiles


@router.post("/runs/{workflow_id}/autonomy")
async def set_autonomy(
    workflow_id: str, request: SetAutonomyRequest
) -> dict[str, Any]:
    """Set the autonomy policy + profile bundle a run's autonomous answerer uses."""
    _load_profile_conversation(request.profile_fixture)  # fail fast on a bad fixture
    _autonomy_config[workflow_id] = request
    return {
        "workflow_id": workflow_id,
        "policy": request.policy.model_dump(),
        "profile_fixture": request.profile_fixture,
    }


@router.post("/runs/{workflow_id}/autonomy/resume")
async def resume_autonomy(workflow_id: str) -> StreamingResponse:
    """Drive the autonomous answerer until escalation or a terminal state,
    streaming one `RunEvent` per decision made."""
    config = _autonomy_config.get(workflow_id)
    if config is None:
        raise HTTPException(
            status_code=400, detail="Call POST /runs/{id}/autonomy first"
        )

    async def event_stream() -> AsyncIterator[str]:
        def emit(event: RunEvent) -> str:
            return f"data: {json.dumps(event.to_dict())}\n\n"

        conversation_history = _load_profile_conversation(config.profile_fixture)
        agent = deps.new_agentic_agent(conversation_history=conversation_history)
        polling_client = await deps.get_polling_client()

        try:
            for _ in range(MAX_AUTONOMOUS_STEPS):
                try:
                    state = await tool_functions.get_workflow_state(
                        workflow_id=workflow_id, temporal_client=polling_client
                    )
                except Exception as exc:  # noqa: BLE001
                    yield emit(
                        RunEvent(
                            type="trace",
                            category="ENGINE",
                            summary="Run not found",
                            detail=str(exc),
                        )
                    )
                    return

                awaiting = state.get("awaiting")
                if not awaiting:
                    yield emit(
                        RunEvent(type="completed", status=state.get("status", "COMPLETE"))
                    )
                    return

                before_token = awaiting.get("token")
                escalation: dict[str, Any] = {}

                async def on_trace(
                    category: str, summary: str, detail: Any = None
                ) -> None:
                    if category == "AGENT" and summary == "Selected Tool: escalate_to_human":
                        escalation.update(detail or {})

                instruction = (
                    "Resolve the field currently awaiting input autonomously, "
                    "using only the seeded profile conversation as your source "
                    "of facts — do not invent values. Policy: autonomy_level="
                    f"{config.policy.autonomy_level}, notify_categories="
                    f"{config.policy.notify_categories}. If you cannot confidently "
                    "resolve this field from the profile, or it falls in a notify "
                    "category, call escalate_to_human with a short reason instead "
                    "of guessing. Otherwise call submit_input."
                )

                try:
                    await agent.respond(instruction, context=state, on_trace=on_trace)
                except Exception as exc:  # noqa: BLE001
                    yield emit(
                        RunEvent(
                            type="trace",
                            category="AGENT",
                            summary="Autonomous step failed",
                            detail=str(exc),
                        )
                    )
                    return

                if escalation:
                    yield emit(
                        RunEvent(
                            type="escalation",
                            category="AGENT",
                            summary="Escalated to human",
                            detail={
                                "reason": escalation.get("reason"),
                                "token": before_token,
                                "prompt": awaiting.get("prompt"),
                                "schema": awaiting.get("schema"),
                            },
                        )
                    )
                    return

                new_state = agent.session_state or {}
                new_awaiting = new_state.get("awaiting")
                new_token = new_awaiting.get("token") if new_awaiting else None
                if new_token == before_token:
                    # Neither submitted nor escalated - stop rather than spin.
                    yield emit(
                        RunEvent(
                            type="escalation",
                            category="AGENT",
                            summary="No progress made; escalating",
                            detail={
                                "reason": "Agent neither submitted nor escalated.",
                                "token": before_token,
                                "prompt": awaiting.get("prompt"),
                                "schema": awaiting.get("schema"),
                            },
                        )
                    )
                    return

                yield emit(
                    RunEvent(
                        type="trace",
                        category="AGENT",
                        summary="Autonomously resolved field",
                        detail={
                            "resolved_from": f"profile.{config.profile_fixture}",
                            "token": before_token,
                        },
                    )
                )

            yield emit(
                RunEvent(
                    type="trace",
                    category="ENGINE",
                    summary=f"Reached max autonomous steps ({MAX_AUTONOMOUS_STEPS})",
                )
            )
        finally:
            await agent.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
