"""FastAPI web server with WebSockets for real-time workflow agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
import uvicorn
from datetime import datetime
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

agent_instance: Any = None
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

    if hasattr(awaiting, "__dict__"):
        awaiting = awaiting.__dict__
    if not isinstance(awaiting, dict):
        return {"kind": None, "options": []}

    schema = awaiting.get("schema") or {}
    if hasattr(schema, "__dict__"):
        schema = schema.__dict__
    if not isinstance(schema, dict):
        schema = {}

    kind = schema.get("kind") or awaiting.get("state_type")
    if kind == "boolean":
        return {"kind": "boolean", "options": ["Yes", "No"]}

    raw_options = (
        awaiting.get("options")
        or schema.get("options")
        or (
            schema.get("schema", {}).get("options")
            if isinstance(schema.get("schema"), dict)
            else None
        )
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


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GOV.UK Chat Assistant</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body {
            font-family: "GDS Transport", Arial, sans-serif;
            margin: 0; padding: 0;
            background-color: #ffffff; color: #0b0c0c;
        }
        .header-banner {
            background-color: #0b0c0c; color: #ffffff;
            padding: 12px 20px; font-weight: bold; font-size: 24px;
            border-bottom: 10px solid #1d70b8;
        }
        .main-layout {
            display: flex; gap: 20px; max-width: 1400px; margin: 20px auto; padding: 0 20px;
        }
        .chat-container { flex: 1; min-width: 0; }
        .sidebar-container { width: 480px; border-left: 2px solid #b1b4b6; padding-left: 20px; }
        .picker-bar {
            background-color: #f3f2f1; border: 2px solid #0b0c0c; padding: 12px; margin-bottom: 15px;
            display: flex; gap: 10px; align-items: center;
        }
        .picker-bar select {
            flex: 1; height: 38px; font-size: 15px; border: 1px solid #0b0c0c; padding: 0 8px;
        }
        .tag { background-color: #1d70b8; color: #fff; padding: 2px 8px; font-weight: bold; font-size: 14px; text-transform: uppercase; }
        .phase-banner { border-bottom: 1px solid #b1b4b6; padding-bottom: 10px; margin-bottom: 20px; }
        #chat-window { border: 2px solid #0b0c0c; background-color: #f8f8f8; height: 440px; overflow-y: auto; padding: 15px; margin-bottom: 15px; }
        #event-window { border: 2px solid #0b0c0c; background-color: #1e1e1e; color: #d4d4d4; font-family: monospace; height: 530px; overflow-y: auto; padding: 12px; font-size: 13px; }
        
        /* Preserve line breaks (\n) and whitespace inside message bubbles */
        .msg { 
            padding: 12px 15px; 
            margin-bottom: 12px; 
            max-width: 85%; 
            line-height: 1.5; 
            font-size: 16px; 
            white-space: pre-wrap; 
            word-wrap: break-word;
        }
        .msg p { margin: 0 0 8px 0; }
        .msg p:last-child { margin-bottom: 0; }
        .msg.user { background-color: #f0f4f8; border-left: 5px solid #1d70b8; margin-left: auto; }
        .msg.assistant { background-color: #ffffff; border-left: 5px solid #00703c; margin-right: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .completion-card { background-color: #d4edda; border: 2px solid #28a745; color: #155724; padding: 15px; font-weight: bold; margin-bottom: 15px; text-align: center; }
        .timeout-badge { background-color: #fff3cd; border: 1px solid #ffeba2; color: #856404; padding: 8px 12px; margin-bottom: 10px; font-weight: bold; }
        .options-container { margin-bottom: 15px; display: flex; flex-wrap: wrap; gap: 8px; }
        
        /* Option Button & Toggle Styles */
        .opt-btn { background-color: #f3f2f1; border: 2px solid #0b0c0c; padding: 8px 14px; font-size: 15px; cursor: pointer; font-weight: bold; transition: background-color 0.15s, color 0.15s; }
        .opt-btn:hover { background-color: #1d70b8; color: white; }
        .opt-btn.multi-chip.selected {
            background-color: #1d70b8;
            color: #ffffff;
            border-color: #003078;
        }
        .opt-btn.submit-multi-btn {
            background-color: #00703c;
            color: #ffffff;
            border-color: #004d25;
            margin-left: 6px;
        }
        .opt-btn.submit-multi-btn:hover {
            background-color: #005a2b;
        }

        .input-row { display: flex; gap: 10px; align-items: center; }
        input[type="text"] { flex-grow: 1; height: 44px; border: 2px solid #0b0c0c; padding: 0 10px; font-size: 16px; }
        button.submit-btn { background-color: #00703c; color: white; border: none; font-weight: bold; font-size: 16px; padding: 0 20px; height: 48px; cursor: pointer; }
        button.file-upload-btn { background-color: #f3f2f1; border: 2px solid #0b0c0c; font-weight: bold; font-size: 14px; padding: 0 15px; height: 48px; cursor: pointer; }
        .trace-entry { margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px dashed #444; }
        .trace-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
        .trace-badge { font-weight: bold; padding: 1px 5px; border-radius: 3px; font-size: 11px; }
        .badge-USER { background-color: #1d70b8; color: white; }
        .badge-AGENT { background-color: #9147ff; color: white; }
        .badge-ENGINE { background-color: #00703c; color: white; }
        .badge-SYSTEM { background-color: #df3079; color: white; }
        .trace-time { color: #888; font-size: 11px; }
        .trace-body { color: #ce9178; word-break: break-all; margin-top: 3px; }
    </style>
</head>
<body>
    <div class="header-banner">GOV.UK</div>
    <div class="main-layout">
        <div class="chat-container">
            <div class="phase-banner">
                <span class="tag">Beta</span> Interactive Workflow & Event Trace
            </div>
            
            <div class="picker-bar">
                <strong>Resume Active Session:</strong>
                <select id="workflow-picker">
                    <option value="">-- Select Active Workflow --</option>
                </select>
                <button onclick="resumeSelectedWorkflow()" style="padding: 6px 12px; cursor: pointer; font-weight: bold;">Resume</button>
            </div>

            <h2>GOV.UK Chat Assistant</h2>
            
            <div id="chat-window">
                <div class="msg assistant">Hello, how can I help you today?</div>
            </div>

            <div id="options-box" class="options-container"></div>
            
            <div class="input-row">
                <input type="file" id="file-input" style="display: none;" onchange="handleFileSelect(event)" />
                <button class="file-upload-btn" onclick="document.getElementById('file-input').click()">Upload Photo</button>
                <input type="text" id="user-input" placeholder="Type your response..." />
                <button class="submit-btn" id="submit-btn" onclick="sendMessage()">Continue</button>
            </div>
        </div>

        <div class="sidebar-container">
            <h2>Execution Events</h2>
            <div id="event-window"></div>
        </div>
    </div>

    <script>
        /* Configure marked library to preserve single line breaks (\n) */
        marked.setOptions({
            breaks: true,
            gfm: true
        });

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${protocol}//${location.host}/ws`);
        const chatWindow = document.getElementById("chat-window");
        const eventWindow = document.getElementById("event-window");
        const optionsBox = document.getElementById("options-box");
        const userInput = document.getElementById("user-input");
        const submitBtn = document.getElementById("submit-btn");
        const workflowPicker = document.getElementById("workflow-picker");

        let selectedMultiOptions = new Set();

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "message") {
                appendMessage(data.role, data.text);
            } else if (data.type === "options") {
                renderOptions(data.options, data.kind);
            } else if (data.type === "active_workflows") {
                populateWorkflowPicker(data.workflows);
            } else if (data.type === "event") {
                appendEvent(data.category, data.summary, data.detail, data.timestamp);
            }
        };

        function appendMessage(role, text) {
            const div = document.createElement("div");
            div.className = `msg ${role}`;
            div.innerHTML = marked.parse(text);
            chatWindow.appendChild(div);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        function appendEvent(category, summary, detail, timestamp) {
            const div = document.createElement("div");
            div.className = "event-entry";
            div.innerHTML = `
                <div class="trace-header">
                    <span class="trace-badge badge-${category}">${category}</span>
                    <span class="trace-time">${timestamp}</span>
                </div>
                <div><strong>${summary}</strong></div>
                <div class="trace-body">${detail ? (typeof detail === 'object' ? JSON.stringify(detail, null, 2) : detail) : ''}</div>
            `;
            eventWindow.appendChild(div);
            eventWindow.scrollTop = eventWindow.scrollHeight;
        }

        function renderOptions(options, kind) {
            optionsBox.innerHTML = "";
            selectedMultiOptions.clear();

            if (!options || options.length === 0) return;

            if (kind === "select_many") {
                // Multi-select mode: Toggle chips + Submit button
                options.forEach(opt => {
                    const btn = document.createElement("button");
                    btn.className = "opt-btn multi-chip";
                    btn.innerText = opt;
                    btn.onclick = () => {
                        if (selectedMultiOptions.has(opt)) {
                            selectedMultiOptions.delete(opt);
                            btn.classList.remove("selected");
                        } else {
                            selectedMultiOptions.add(opt);
                            btn.classList.add("selected");
                        }
                    };
                    optionsBox.appendChild(btn);
                });

                const submitSelectionsBtn = document.createElement("button");
                submitSelectionsBtn.className = "opt-btn submit-multi-btn";
                submitSelectionsBtn.innerText = "Confirm Selections ✓";
                submitSelectionsBtn.onclick = () => {
                    if (selectedMultiOptions.size === 0) return;
                    const combinedSelection = Array.from(selectedMultiOptions).join(", ");
                    sendText(combinedSelection);
                };
                optionsBox.appendChild(submitSelectionsBtn);

            } else {
                // Single-select mode: Immediate submission on click
                options.forEach(opt => {
                    const btn = document.createElement("button");
                    btn.className = "opt-btn";
                    btn.innerText = opt;
                    btn.onclick = () => sendText(opt);
                    optionsBox.appendChild(btn);
                });
            }
        }

        function populateWorkflowPicker(workflows) {
            workflowPicker.innerHTML = '<option value="">-- Select Active Workflow --</option>';
            workflows.forEach(wf => {
                const opt = document.createElement("option");
                opt.value = wf.id;
                opt.innerText = `${wf.id} (${wf.status})`;
                workflowPicker.appendChild(opt);
            });
        }

        function resumeSelectedWorkflow() {
            const selectedId = workflowPicker.value;
            if (!selectedId) return;
            ws.send(JSON.stringify({ action: "resume", workflow_id: selectedId }));
        }

        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const filePayload = `[Uploaded File: ref='${file.name}', content_type='${file.type || 'image/jpeg'}', bytes=${file.size}]`;
            appendMessage("user", `Uploaded: ${file.name}`);
            ws.send(JSON.stringify({ message: filePayload }));
            event.target.value = "";
        }

        function sendText(text) {
            if (!text.trim()) return;
            appendMessage("user", text);
            ws.send(JSON.stringify({ message: text }));
            userInput.value = "";
            optionsBox.innerHTML = "";
        }

        function sendMessage() {
            sendText(userInput.value);
        }

        userInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
"""


@app.get("/")
async def get_index() -> HTMLResponse:
    return HTMLResponse(HTML_TEMPLATE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    session_id = str(uuid.uuid4())
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
        if not agent_instance:
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

                if not active_workflow_id or not agent_instance:
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
                        clean_msg = msg_text

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
                    agent_instance._session_state = None
                    last_seen_index = 0
                    handled_tokens.clear()

                    await refresh_active_workflows()
                    continue

                if token and token not in handled_tokens:
                    handled_tokens.add(token)
                    prompt_text = awaiting.get("prompt", "")
                    clean_prompt = prompt_text
                    if clean_prompt:
                        await websocket.send_json(
                            {
                                "type": "message",
                                "role": "assistant",
                                "text": clean_prompt,
                            }
                        )
                        await emit_event(
                            "ENGINE",
                            f"Awaiting InputState [{token}]",
                            {
                                "prompt": clean_prompt,
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
                if resume_id and agent_instance:
                    active_workflow_id = resume_id
                    workflow_id_var.set(resume_id)
                    await emit_event("USER", "Resuming Selected Workflow", resume_id)
                    polling_client = await _get_polling_client()
                    session_state = await tool_functions.get_workflow_state(
                        workflow_id=resume_id, temporal_client=polling_client
                    )
                    agent_instance._update_session_state(resume_id, session_state)
                    last_seen_index = 0
                    handled_tokens.clear()
                continue

            user_msg = payload.get("message", "").strip()
            if not user_msg or not agent_instance:
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
                agent_response = await agent_instance.respond(
                    user_msg, context=session_state, on_trace=emit_event
                )
                logger.info("Agent response text=%r", agent_response)

                session_state = getattr(agent_instance, "session_state", session_state)

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

    global agent_instance

    provider = create_agent_provider(session_processor=session_processor)
    trace.set_tracer_provider(provider)

    workflow_server_url = os.environ.get("WORKFLOW_SERVER_URL", "http://localhost:8080")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")
    region_name = os.environ.get("AWS_REGION", "eu-west-2")
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

    agent_instance = WorkflowAgent(
        workflow_server_url=workflow_server_url,
        model_id=model_id,
        region_name=region_name,
        temporal_address=temporal_address,
    )

    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
