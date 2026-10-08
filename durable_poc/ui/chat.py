"""FastAPI web server with WebSockets for real-time workflow agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
import uvicorn
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace, baggage
from opentelemetry.context import attach, detach

from temporalio.client import Client as TemporalClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from agent import tools as tool_functions
from agent.agent import WorkflowAgent
from src.telemetry import SessionSpanProcessor, create_agent_provider, session_id_var, workflow_id_var

logger = logging.getLogger(__name__)

app = FastAPI(title="GOV.UK Chat Assistant")
INDEX_HTML = (
    Path(__file__).parent
    / "index.html"
)

_polling_client: TemporalClient | None = None


async def _get_polling_client() -> TemporalClient:
    """Temporal client for background polling — no TracingInterceptor."""
    global _polling_client
    if _polling_client is None:
        temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
        _polling_client = await TemporalClient.connect(temporal_address)
    return _polling_client


def get_options_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Extract human-readable options and schema kind generically from current awaiting state."""
    if not state:
        return {"kind": None, "options": []}

    awaiting = state.get("awaiting")
    if not awaiting:
        return {"kind": None, "options": []}

    if not isinstance(awaiting, dict):
        return {"kind": None, "options": []}

    schema = awaiting.get("schema") or {}

    fields = schema.get("fields", [])
    interactive_fields = [f for f in fields if f.get("type") != "display"]

    if len(interactive_fields) == 1:

        field_type = interactive_fields[0].get("type")

        if field_type == "choice":
            kind = "select_one"

        elif field_type == "multi_choice":
            kind = "select_many"

        else:
            kind = field_type
    else:
        kind = schema.get("kind") or awaiting.get("state_type")

    if not isinstance(schema, dict):
        schema = {}

    if kind == "boolean":
        return {"kind": "boolean", "options": ["Yes", "No"]}

    raw_options = (
        awaiting.get("options")
        or schema.get("options")
        or []
    )

    if not isinstance(raw_options, list) or not raw_options:
        return {"kind": kind, "options": []}

    label_key = schema.get("label_key")
    value_key = schema.get("value_key")

    choices = []
    for opt in raw_options:
        if isinstance(opt, dict):
            label = None
            if label_key and opt.get(label_key) is not None:
                label = opt.get(label_key)

            if label is None:
                label = (
                    opt.get("label")
                    or opt.get("single_line")
                    or opt.get("name")
                    or opt.get("title")
                    or opt.get("description")
                    or (opt.get(value_key) if value_key else None)
                    or opt.get("id")
                    or opt.get("value")
                )

            if label is None:
                str_vals = [v for v in opt.values() if isinstance(v, str)]
                label = str_vals[0] if str_vals else str(opt)

            choices.append(str(label))
        elif hasattr(opt, "label"):
            choices.append(str(getattr(opt, "label")))
        elif hasattr(opt, "value"):
            choices.append(str(getattr(opt, "value")))
        else:
            choices.append(str(opt))

    return {"kind": kind, "options": choices}


def create_agent() -> WorkflowAgent:
    workflow_server_url = os.environ.get(
        "WORKFLOW_SERVER_URL",
        "http://Workfl-Workf-CwPhUxgpA91a-749675269.eu-west-2.elb.amazonaws.com",
    )
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-sonnet-4-6",
    )
    region_name = os.environ.get(
        "AWS_REGION",
        "eu-west-2",
    )
    temporal_address = os.environ.get(
        "TEMPORAL_ADDRESS",
        "localhost:7233",
    )

    return WorkflowAgent(
        workflow_server_url=workflow_server_url,
        model_id=model_id,
        region_name=region_name,
        temporal_address=temporal_address,
    )


@app.get("/")
async def get_index() -> HTMLResponse:
    """
    Serve the GOV.UK chat frontend.
    """

    return HTMLResponse(
        INDEX_HTML.read_text(
            encoding="utf-8",
        )
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    agent = create_agent()
    session_id = str(uuid.uuid4())
    logger.info("Created agent=%s session=%s", id(agent), session_id)
    session_id_var.set(session_id)
    ctx = baggage.set_baggage("session_id", session_id)
    token = attach(ctx)

    otel_tracer = trace.get_tracer(__name__)

    session_state: dict[str, Any] | None = None
    active_workflow_id: str | None = None
    last_seen_index = 0
    handled_tokens: set[str] = set()

    async def emit_event(category: str, summary: str, detail: Any = None) -> None:
        try:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            await websocket.send_json(
                {
                    "type": "event",
                    "category": category,
                    "summary": summary,
                    "detail": detail,
                    "timestamp": ts,
                }
            )
        except Exception:
            pass

    async def refresh_active_workflows() -> None:
        """Send list of active workflows to dropdown picker."""
        if not agent:
            return
        try:
            polling_client = await _get_polling_client()
            active_list = await tool_functions.list_active_workflows(
                temporal_client=polling_client
            )
            await websocket.send_json(
                {"type": "active_workflows", "workflows": active_list}
            )
        except Exception:
            pass

    await refresh_active_workflows()

    async def stream_background_events() -> None:
        """Direct Workflow Renderer - Sole emitter for all assistant messages."""
        nonlocal session_state, active_workflow_id, last_seen_index, handled_tokens

        while True:
            try:
                await asyncio.sleep(0.5)

                if not active_workflow_id or not agent:
                    continue

                try:
                    polling_client = await _get_polling_client()
                    updated_state = await tool_functions.get_workflow_state(
                        workflow_id=active_workflow_id,
                        temporal_client=polling_client,
                    )
                except Exception:
                    continue

                session_state = updated_state
                transcript = updated_state.get("transcript", [])
                current_len = len(transcript)
                awaiting = updated_state.get("awaiting")
                token = awaiting.get("token") if awaiting else None

                execution_status = updated_state.get("status", "RUNNING")

                if current_len > last_seen_index:
                    for idx in range(last_seen_index, current_len):
                        entry = transcript[idx]
                        msg_text = (
                            entry.get("message")
                            if isinstance(entry, dict)
                            else getattr(entry, "message", "")
                        )
                        clean_msg = str(
                            msg_text or ""
                        ).strip()

                        if not clean_msg:
                            continue


                        if clean_msg.startswith("[ENGINE LOG]"):
                            await emit_event(
                                "ENGINE",
                                "FSM Execution Event",
                                clean_msg.replace("[ENGINE LOG]", "").strip(),
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "text": clean_msg,
                                }
                            )
                            await emit_event(
                                "ENGINE", "OutputState Transcript Emitted", clean_msg
                            )

                    last_seen_index = current_len
                
                if not awaiting and execution_status in (
                    "COMPLETED",
                    "FAILED",
                    "TERMINATED",
                ):
                    await emit_event(
                        "ENGINE",
                        "Workflow Execution Completed",
                        {"status": execution_status},
                    )
                    active_workflow_id = None
                    session_state = None
                    agent._session_state = None
                    last_seen_index = 0
                    handled_tokens.clear()

                    await refresh_active_workflows()
                    continue

                if token and token not in handled_tokens:
                    handled_tokens.add(token)
                    schema = awaiting.get("schema", {})

                    message_parts = []

                    for field in schema.get("fields", []):

                        if field.get("type") != "display":
                            continue

                        label = field.get("label")
                        value = field.get("value")

                        if label and value is not None:
                            message_parts.append(
                                f"**{label}:** {value}"
                            )

                    prompt = awaiting.get("prompt")

                    if prompt:
                        message_parts.append("")
                        message_parts.append(prompt)

                    rendered_message = "\n".join(
                        message_parts
                    ).strip()

                    if rendered_message:
                        await websocket.send_json(
                            {
                                "type": "message",
                                "role": "assistant",
                                "text": rendered_message,
                            }
                        )

                        await emit_event(
                            "ENGINE",
                            f"Awaiting InputState [{token}]",
                            {
                                "prompt": rendered_message,
                                "schema": awaiting.get("schema"),
                            },
                        )

                    opts_payload = get_options_from_state(session_state)
                    await websocket.send_json(
                        {
                            "type": "options",
                            "kind": opts_payload["kind"],
                            "options": opts_payload["options"],
                        }
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.debug("Error in background polling task: %s", e)

    poll_task = asyncio.create_task(stream_background_events())

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "resume":
                resume_id = payload.get("workflow_id")
                if resume_id and agent:
                    active_workflow_id = resume_id
                    workflow_id_var.set(resume_id)
                    await emit_event("USER", "Resuming Selected Workflow", resume_id)
                    polling_client = await _get_polling_client()
                    session_state = await tool_functions.get_workflow_state(
                        workflow_id=resume_id, temporal_client=polling_client
                    )
                    agent._update_session_state(resume_id, session_state)
                    last_seen_index = 0
                    handled_tokens.clear()
                continue

            user_msg = payload.get("message", "").strip()
            if not user_msg or not agent:
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
                await emit_event("USER", "Submitted Natural Language Input", user_msg)

                prev_token = (
                    session_state.get("awaiting", {}).get("token")
                    if session_state and session_state.get("awaiting")
                    else None
                )

                await emit_event("AGENT", "Invoking Bedrock LLM with user context...")
                logger.info("agent=%s workflow=%s", id(agent), active_workflow_id)
                agent_response = await agent.respond(
                    user_msg, context=session_state, on_trace=emit_event
                )
                logger.info("Agent response text=%r", agent_response)

                session_state = getattr(agent, "session_state", session_state)

                workflow_started = (session_state and session_state.get("workflow_id"))

                if (agent_response and agent_response.strip() and not workflow_started
                ):
                    await websocket.send_json(
                        {
                            "type": "message",
                            "role": "assistant",
                            "text": agent_response,
                        }
                    )

                if session_state and session_state.get("workflow_id"):
                    new_workflow_id = session_state.get("workflow_id")

                    if new_workflow_id != active_workflow_id:
                        active_workflow_id = new_workflow_id
                        workflow_id_var.set(active_workflow_id)

                        last_seen_index = 0
                        handled_tokens.clear()

                new_token = (
                    session_state.get("awaiting", {}).get("token")
                    if session_state and session_state.get("awaiting")
                    else None
                )

                if (
                    prev_token
                    and new_token
                    and prev_token == new_token
                    and agent_response
                    and agent_response.strip()
                ):
                    clean_warning = agent_response
                    if clean_warning:
                        await websocket.send_json(
                            {
                                "type": "message",
                                "role": "assistant",
                                "text": clean_warning,
                            }
                        )
                        await emit_event(
                            "AGENT", "Agent emitted validation warning text", clean_warning
                        )

            opts_payload = get_options_from_state(session_state)
            await websocket.send_json(
                {
                    "type": "options",
                    "kind": opts_payload["kind"],
                    "options": opts_payload["options"],
                }
            )
            await refresh_active_workflows()

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    finally:
        detach(token)
        poll_task.cancel()


session_processor = SessionSpanProcessor()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    provider = create_agent_provider(session_processor=session_processor)
    trace.set_tracer_provider(provider)

    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
