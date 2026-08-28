"""FastAPI web server with WebSockets for real-time workflow agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uvicorn
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from agent import tools as tool_functions
from agent.agent import WorkflowAgent

logger = logging.getLogger(__name__)

app = FastAPI(title="GOV.UK Chat Assistant")

agent_instance: Any = None


def clean_text_pipes(text: str) -> str:
    """Strip leading/trailing standalone vertical pipe characters from text lines."""
    if not text:
        return ""
    lines = [re.sub(r"^\s*\|\s*|\s*\|\s*$", "", line) for line in text.splitlines()]
    return "\n".join(lines).strip()


def get_options_from_state(state: dict[str, Any] | None) -> list[str]:
    """Extract human-readable options generically from current awaiting schema."""
    if not state:
        return []
    awaiting = state.get("awaiting")
    if not awaiting:
        return []
    if hasattr(awaiting, "__dict__"):
        awaiting = awaiting.__dict__
    if not isinstance(awaiting, dict):
        return []

    schema = awaiting.get("schema") or {}
    if hasattr(schema, "__dict__"):
        schema = schema.__dict__
    if not isinstance(schema, dict):
        schema = {}

    kind = schema.get("kind")
    if kind == "boolean":
        return ["Yes", "No"]

    if kind == "enum":
        labels = schema.get("labels") or {}
        values = schema.get("values") or []
        if isinstance(values, list):
            return [str(labels.get(v, v)) for v in values]

    if kind in ("select_one", "select_many"):
        raw_options = awaiting.get("options") or schema.get("options") or []
        if not isinstance(raw_options, list):
            return []

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
                        or (opt.get(value_key) if value_key else None)
                        or opt.get("id")
                        or opt.get("uprn")
                    )

                if label is None:
                    str_vals = [v for v in opt.values() if isinstance(v, str)]
                    label = str_vals[0] if str_vals else str(opt)

                choices.append(str(label))
            else:
                choices.append(str(opt))
        return choices

    return []


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
        #trace-window { border: 2px solid #0b0c0c; background-color: #1e1e1e; color: #d4d4d4; font-family: monospace; height: 530px; overflow-y: auto; padding: 12px; font-size: 13px; }
        .msg { padding: 12px 15px; margin-bottom: 12px; max-width: 85%; line-height: 1.4; font-size: 16px; }
        .msg.user { background-color: #f0f4f8; border-left: 5px solid #1d70b8; margin-left: auto; }
        .msg.assistant { background-color: #ffffff; border-left: 5px solid #00703c; margin-right: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .completion-card { background-color: #d4edda; border: 2px solid #28a745; color: #155724; padding: 15px; font-weight: bold; margin-bottom: 15px; text-align: center; }
        .timeout-badge { background-color: #fff3cd; border: 1px solid #ffeba2; color: #856404; padding: 8px 12px; margin-bottom: 10px; font-weight: bold; }
        .options-container { margin-bottom: 15px; display: flex; flex-wrap: wrap; gap: 8px; }
        .opt-btn { background-color: #f3f2f1; border: 1px solid #0b0c0c; padding: 8px 14px; font-size: 15px; cursor: pointer; }
        .opt-btn:hover { background-color: #dbdad9; }
        .input-row { display: flex; gap: 10px; align-items: center; }
        input[type="text"] { flex-grow: 1; height: 44px; border: 2px solid #0b0c0c; padding: 0 10px; font-size: 16px; }
        button.submit-btn { background-color: #00703c; color: white; border: none; font-weight: bold; font-size: 16px; padding: 0 20px; height: 48px; cursor: pointer; }
        /* Sidebar Styles */
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
            
            <!-- Issue 3.8: Resume Workflow Picker -->
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
            
            <!-- Issue 3.5 & 3.6: Dynamic Status Containers -->
            <div id="completion-box"></div>
            <div id="timeout-box"></div>
            <div id="options-box" class="options-container"></div>
            
            <div class="input-row">
                <input type="file" id="file-input" style="display: none;" onchange="handleFileSelect(event)" />
                <button class="file-upload-btn" onclick="document.getElementById('file-input').click()">Upload Photo</button>
                <input type="text" id="user-input" placeholder="Type your response..." />
                <button class="submit-btn" id="submit-btn" onclick="sendMessage()">Continue</button>
            </div>
        </div>

        <div class="sidebar-container">
            <h2>Execution Event Trace</h2>
            <div id="trace-window"></div>
        </div>
    </div>

    <script>
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${protocol}//${location.host}/ws`);
        const chatWindow = document.getElementById("chat-window");
        const traceWindow = document.getElementById("trace-window");
        const optionsBox = document.getElementById("options-box");
        const timeoutBox = document.getElementById("timeout-box");
        const completionBox = document.getElementById("completion-box");
        const userInput = document.getElementById("user-input");
        const submitBtn = document.getElementById("submit-btn");
        const workflowPicker = document.getElementById("workflow-picker");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "message") {
                appendMessage(data.role, data.text);
            } else if (data.type === "options") {
                renderOptions(data.options);
            } else if (data.type === "timeout") {
                renderTimeout(data.seconds);
            } else if (data.type === "completed") {
                renderCompletion(data.status);
            } else if (data.type === "active_workflows") {
                populateWorkflowPicker(data.workflows);
            } else if (data.type === "trace") {
                appendTrace(data.category, data.summary, data.detail, data.timestamp);
            }
        };

        function appendMessage(role, text) {
            const div = document.createElement("div");
            div.className = `msg ${role}`;
            div.innerHTML = marked.parse(text);
            chatWindow.appendChild(div);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        function appendTrace(category, summary, detail, timestamp) {
            const div = document.createElement("div");
            div.className = "trace-entry";
            div.innerHTML = `
                <div class="trace-header">
                    <span class="trace-badge badge-${category}">${category}</span>
                    <span class="trace-time">${timestamp}</span>
                </div>
                <div><strong>${summary}</strong></div>
                <div class="trace-body">${detail ? (typeof detail === 'object' ? JSON.stringify(detail, null, 2) : detail) : ''}</div>
            `;
            traceWindow.appendChild(div);
            traceWindow.scrollTop = traceWindow.scrollHeight;
        }

        function renderOptions(options) {
            optionsBox.innerHTML = "";
            if (options && options.length > 0) {
                options.forEach(opt => {
                    const btn = document.createElement("button");
                    btn.className = "opt-btn";
                    btn.innerText = opt;
                    btn.onclick = () => sendText(opt);
                    optionsBox.appendChild(btn);
                });
            }
        }

        /* Issue 3.5: Timeout Display */
        function renderTimeout(seconds) {
            if (seconds) {
                const mins = Math.ceil(seconds / 60);
                timeoutBox.innerHTML = `<div class="timeout-badge">⏱ Please respond within ${mins} minute(s)</div>`;
            } else {
                timeoutBox.innerHTML = "";
            }
        }

        /* Issue 3.6: Completion Card */
        function renderCompletion(status) {
            completionBox.innerHTML = `<div class="completion-card">🏁 Workflow Completed (Status: ${status || 'SUCCESS'})</div>`;
            userInput.disabled = true;
            submitBtn.disabled = true;
            optionsBox.innerHTML = "";
            timeoutBox.innerHTML = "";
        }

        /* Issue 3.8: Resume Workflow Picker */
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
            
            const filePayload = `[Uploaded File: content_type='${file.type || 'image/jpeg'}', bytes=${file.size}]`;
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
            timeoutBox.innerHTML = "";
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
async def get_index():
    return HTMLResponse(HTML_TEMPLATE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    session_state: dict[str, Any] | None = None
    active_workflow_id: str | None = None
    last_seen_index = 0
    handled_tokens = set()

    async def emit_trace(category: str, summary: str, detail: Any = None):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        await websocket.send_json(
            {
                "type": "trace",
                "category": category,
                "summary": summary,
                "detail": detail,
                "timestamp": ts,
            }
        )

    async def refresh_active_workflows():
        """Issue 3.8: Send list of active workflows to dropdown picker."""
        try:
            temporal_client = await agent_instance._get_temporal_client()
            active_list = await tool_functions.list_active_workflows(
                temporal_client=temporal_client
            )
            await websocket.send_json(
                {"type": "active_workflows", "workflows": active_list}
            )
        except Exception:
            pass

    await refresh_active_workflows()

    async def stream_background_events():
        """Direct Workflow Renderer - Sole emitter for all assistant messages."""
        nonlocal session_state, active_workflow_id, last_seen_index

        while True:
            await asyncio.sleep(0.5)

            if session_state and session_state.get("workflow_id"):
                active_workflow_id = session_state.get("workflow_id")

            if not active_workflow_id:
                continue

            try:
                temporal_client = await agent_instance._get_temporal_client()
                updated_state = await tool_functions.get_workflow_state(
                    workflow_id=active_workflow_id,
                    temporal_client=temporal_client,
                )
            except Exception:
                continue

            session_state = updated_state
            transcript = updated_state.get("transcript", [])
            current_len = len(transcript)
            awaiting = updated_state.get("awaiting")
            token = awaiting.get("token") if awaiting else None

            execution_status = updated_state.get("status", "RUNNING")
            if not awaiting and execution_status in (
                "COMPLETED",
                "FAILED",
                "TERMINATED",
            ):
                await websocket.send_json(
                    {"type": "completed", "status": execution_status}
                )
                await emit_trace(
                    "ENGINE",
                    "Workflow Execution Completed",
                    {"status": execution_status},
                )

            if current_len > last_seen_index:
                for idx in range(last_seen_index, current_len):
                    entry = transcript[idx]
                    msg_text = (
                        entry.get("message")
                        if isinstance(entry, dict)
                        else getattr(entry, "message", "")
                    )
                    clean_msg = clean_text_pipes(msg_text)

                    if clean_msg.startswith("[ENGINE LOG]"):
                        await emit_trace(
                            "ENGINE",
                            "FSM Execution Event",
                            clean_msg.replace("[ENGINE LOG]", "").strip(),
                        )
                    else:
                        await websocket.send_json(
                            {"type": "message", "role": "assistant", "text": clean_msg}
                        )
                        await emit_trace(
                            "ENGINE", "OutputState Transcript Emitted", clean_msg
                        )

                last_seen_index = current_len

            if token and token not in handled_tokens:
                handled_tokens.add(token)
                prompt_text = awaiting.get("prompt", "")
                clean_prompt = clean_text_pipes(prompt_text)
                if clean_prompt:
                    await websocket.send_json(
                        {"type": "message", "role": "assistant", "text": clean_prompt}
                    )
                    await emit_trace(
                        "ENGINE",
                        f"Awaiting InputState [{token}]",
                        {
                            "prompt": clean_prompt,
                            "schema": awaiting.get("schema"),
                        },
                    )

                options = get_options_from_state(session_state)
                await websocket.send_json({"type": "options", "options": options})

                timeout_secs = awaiting.get("timeout_seconds")
                await websocket.send_json({"type": "timeout", "seconds": timeout_secs})

    poll_task = asyncio.create_task(stream_background_events())

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "resume":
                resume_id = payload.get("workflow_id")
                if resume_id:
                    active_workflow_id = resume_id
                    await emit_trace("USER", "Resuming Selected Workflow", resume_id)
                    temporal_client = await agent_instance._get_temporal_client()
                    session_state = await tool_functions.get_workflow_state(
                        workflow_id=resume_id, temporal_client=temporal_client
                    )
                    agent_instance._update_session_state(resume_id, session_state)
                    last_seen_index = 0
                    handled_tokens.clear()
                continue

            user_msg = payload.get("message", "").strip()
            if not user_msg:
                continue

            await emit_trace("USER", "Submitted Natural Language Input", user_msg)

            prev_token = (
                session_state.get("awaiting", {}).get("token")
                if session_state and session_state.get("awaiting")
                else None
            )

            await emit_trace("AGENT", "Invoking Bedrock LLM with user context...")
            agent_response = await agent_instance.respond(
                user_msg, context=session_state, on_trace=emit_trace
            )
            session_state = getattr(agent_instance, "session_state", session_state)

            if session_state and session_state.get("workflow_id"):
                active_workflow_id = session_state.get("workflow_id")

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
                clean_warning = clean_text_pipes(agent_response)
                if clean_warning:
                    await websocket.send_json(
                        {
                            "type": "message",
                            "role": "assistant",
                            "text": clean_warning,
                        }
                    )
                    await emit_trace(
                        "AGENT", "Agent emitted validation warning text", clean_warning
                    )

            options = get_options_from_state(session_state)
            await websocket.send_json({"type": "options", "options": options})
            await refresh_active_workflows()

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    finally:
        poll_task.cancel()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    global agent_instance

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
