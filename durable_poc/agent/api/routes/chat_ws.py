"""WebSocket chat route: `WorkflowAgent`-mediated natural-language turns.

Generalizes `agent/chat.py`'s `/ws` handler — same message vocabulary
(`message`/`options`/`active_workflows`/`trace`/`timeout`/`completed`, and
the client actions `resume`), with the embedded HTML UI stripped out and
the polling loop replaced by `events.watch_run`. `/voice` is expected to
reuse this same vocabulary with an added audio codec layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from opentelemetry import baggage, trace
from opentelemetry.context import attach, detach

from agent import tools as tool_functions
from agent.api import deps
from agent.api.events import clean_text_pipes, get_options_from_state, watch_run
from src.telemetry import session_id_var, workflow_id_var

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket) -> None:
    """One chat session: one `WorkflowAgent`, one optional active run."""
    await websocket.accept()

    session_id = str(uuid.uuid4())
    session_id_var.set(session_id)
    otel_token = attach(baggage.set_baggage("session_id", session_id))
    otel_tracer = trace.get_tracer(__name__)

    agent_instance = deps.new_workflow_agent()
    session_state: dict[str, Any] | None = None
    active_workflow_id: str | None = None
    watch_task: asyncio.Task[None] | None = None

    async def emit_trace(category: str, summary: str, detail: Any = None) -> None:
        try:
            await websocket.send_json(
                {
                    "type": "trace",
                    "category": category,
                    "summary": summary,
                    "detail": detail,
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                }
            )
        except Exception:
            pass

    async def refresh_active_workflows() -> None:
        try:
            polling_client = await deps.get_polling_client()
            active_list = await tool_functions.list_active_workflows(
                temporal_client=polling_client
            )
            await websocket.send_json(
                {"type": "active_workflows", "workflows": active_list}
            )
        except Exception:
            pass

    async def watch_active_run(workflow_id: str) -> None:
        polling_client = await deps.get_polling_client()
        async for event in watch_run(workflow_id, polling_client):
            if event.type == "message":
                await websocket.send_json(
                    {"type": "message", "role": event.role, "text": event.text}
                )
            elif event.type == "trace":
                await emit_trace(event.category or "ENGINE", event.summary or "", event.detail)
            elif event.type == "options":
                await websocket.send_json(
                    {"type": "options", "kind": event.kind, "options": event.options}
                )
            elif event.type == "timeout":
                await websocket.send_json({"type": "timeout", "seconds": event.seconds})
            elif event.type == "completed":
                await websocket.send_json({"type": "completed", "status": event.status})
                return

    def restart_watch(workflow_id: str) -> None:
        nonlocal watch_task
        if watch_task is not None:
            watch_task.cancel()
        watch_task = asyncio.create_task(watch_active_run(workflow_id))

    await refresh_active_workflows()

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "resume":
                resume_id = payload.get("workflow_id")
                if resume_id:
                    active_workflow_id = resume_id
                    workflow_id_var.set(resume_id)
                    await emit_trace("USER", "Resuming Selected Workflow", resume_id)
                    polling_client = await deps.get_polling_client()
                    session_state = await tool_functions.get_workflow_state(
                        workflow_id=resume_id, temporal_client=polling_client
                    )
                    agent_instance._update_session_state(resume_id, session_state)
                    restart_watch(resume_id)
                continue

            user_msg = payload.get("message", "").strip()
            if not user_msg:
                continue

            if active_workflow_id:
                workflow_id_var.set(active_workflow_id)

            with otel_tracer.start_as_current_span(
                "user_turn",
                attributes={
                    "session_id": session_id,
                    "temporalWorkflowID": active_workflow_id or "",
                    "user_message_preview": user_msg[:100],
                },
            ):
                await emit_trace("USER", "Submitted Natural Language Input", user_msg)
                await emit_trace("AGENT", "Invoking Bedrock LLM with user context...")
                agent_response = await agent_instance.respond(
                    user_msg, context=session_state, on_trace=emit_trace
                )
                session_state = getattr(agent_instance, "session_state", session_state)

                if session_state and session_state.get("workflow_id"):
                    new_wf_id = session_state.get("workflow_id")
                    if new_wf_id != active_workflow_id:
                        active_workflow_id = new_wf_id
                        workflow_id_var.set(active_workflow_id)
                        restart_watch(active_workflow_id)

                if agent_response and agent_response.strip():
                    clean_response = clean_text_pipes(agent_response)
                    if clean_response:
                        await websocket.send_json(
                            {"type": "message", "role": "assistant", "text": clean_response}
                        )
                        await emit_trace("AGENT", "Agent emitted response text", clean_response)

            opts_payload = get_options_from_state(session_state)
            await websocket.send_json(
                {"type": "options", "kind": opts_payload["kind"], "options": opts_payload["options"]}
            )
            await refresh_active_workflows()

    except WebSocketDisconnect:
        logger.info("Chat WebSocket connection closed")
    finally:
        if watch_task is not None:
            watch_task.cancel()
        await agent_instance.close()
        detach(otel_token)
