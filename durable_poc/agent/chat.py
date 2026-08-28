"""FastAPI web server with WebSockets for real-time workflow agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uvicorn
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
    if not awaiting or not isinstance(awaiting, dict):
        return []

    schema = awaiting.get("schema", {})
    if not isinstance(schema, dict):
        schema = {}
    kind = schema.get("kind")

    # 1. Handle Enum options
    if kind == "enum":
        labels = schema.get("labels", {})
        values = schema.get("values", [])
        if not isinstance(labels, dict):
            labels = {}
        if isinstance(values, list):
            return [str(labels.get(v, v)) for v in values]

    # 2. Generic Selection Handler (select_one, select_many, lists)
    if kind in ("select_one", "select_many"):
        raw_options = awaiting.get("options")
        options = raw_options if isinstance(raw_options, list) else []

        label_key = schema.get("label_key")
        value_key = schema.get("value_key")

        choices = []
        for opt in options:
            if isinstance(opt, dict):
                label = None
                if label_key and opt.get(label_key) is not None:
                    label = opt.get(label_key)
                else:
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

    # 3. Handle Boolean choices
    if kind == "boolean":
        return ["Yes", "No"]

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
        .container {
            max-width: 800px; margin: 20px auto; padding: 0 20px;
        }
        .tag {
            background-color: #1d70b8; color: #fff; padding: 2px 8px;
            font-weight: bold; font-size: 14px; text-transform: uppercase;
        }
        .phase-banner {
            border-bottom: 1px solid #b1b4b6; padding-bottom: 10px; margin-bottom: 20px;
        }
        #chat-window {
            border: 2px solid #0b0c0c; background-color: #f8f8f8;
            height: 420px; overflow-y: auto; padding: 15px; margin-bottom: 20px;
        }
        .msg {
            padding: 12px 15px; margin-bottom: 12px; max-width: 80%;
            line-height: 1.4; font-size: 16px;
        }
        .msg ul { margin: 8px 0; padding-left: 20px; }
        .msg p { margin: 0 0 8px 0; }
        .msg p:last-child { margin-bottom: 0; }
        .msg.user {
            background-color: #f0f4f8; border-left: 5px solid #1d70b8; margin-left: auto;
        }
        .msg.assistant {
            background-color: #ffffff; border-left: 5px solid #00703c; margin-right: auto;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .options-container {
            margin-bottom: 15px; display: flex; flex-wrap: wrap; gap: 8px;
        }
        .opt-btn {
            background-color: #f3f2f1; border: 1px solid #0b0c0c;
            padding: 8px 14px; font-size: 15px; cursor: pointer; text-align: left;
        }
        .opt-btn:hover { background-color: #dbdad9; }
        .input-row { display: flex; gap: 10px; align-items: center; }
        input[type="text"] {
            flex-grow: 1; height: 44px; border: 2px solid #0b0c0c; padding: 0 10px; font-size: 16px;
        }
        .file-upload-btn {
            background-color: #ffffff; border: 2px dashed #0b0c0c; padding: 10px;
            cursor: pointer; font-weight: bold;
        }
        button.submit-btn {
            background-color: #00703c; color: white; border: none; font-weight: bold;
            font-size: 16px; padding: 0 20px; height: 48px; cursor: pointer;
        }
        button.submit-btn:hover { background-color: #005a30; }
    </style>
</head>
<body>
    <div class="header-banner">GOV.UK</div>
    <div class="container">
        <div class="phase-banner">
            <span class="tag">Beta</span> This is a new digital service – your feedback helps us to improve it.
        </div>
        <h1>GOV.UK Chat Assistant</h1>

        <div id="chat-window">
            <div class="msg assistant">Hello, how can I help you today?</div>
        </div>
        <div id="options-box" class="options-container"></div>

        <div class="input-row">
            <input type="file" id="file-input" style="display: none;" onchange="handleFileSelect(event)" />
            <button class="file-upload-btn" onclick="document.getElementById('file-input').click()">Upload Photo</button>
            <input type="text" id="user-input" placeholder="Type your response..." />
            <button class="submit-btn" onclick="sendMessage()">Continue</button>
        </div>
    </div>

    <script>
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${protocol}//${location.host}/ws`);
        const chatWindow = document.getElementById("chat-window");
        const optionsBox = document.getElementById("options-box");
        const userInput = document.getElementById("user-input");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === "message") {
                appendMessage(data.role, data.text);
            } else if (data.type === "options") {
                renderOptions(data.options);
            }
        };

        function appendMessage(role, text) {
            const div = document.createElement("div");
            div.className = `msg ${role}`;
            div.innerHTML = marked.parse(text);
            chatWindow.appendChild(div);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        function renderOptions(options) {
            optionsBox.innerHTML = "";
            options.forEach(opt => {
                const btn = document.createElement("button");
                btn.className = "opt-btn";
                btn.innerText = opt;
                btn.onclick = () => sendText(opt);
                optionsBox.appendChild(btn);
            });
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

            # STREAM SYSTEM TRANSCRIPT ENTRIES DIRECTLY FROM TEMPORAL
            if current_len > last_seen_index:
                for idx in range(last_seen_index, current_len):
                    entry = transcript[idx]
                    msg_text = (
                        entry.get("message")
                        if isinstance(entry, dict)
                        else getattr(entry, "message", "")
                    )
                    clean_msg = clean_text_pipes(msg_text)
                    if clean_msg:
                        await websocket.send_json(
                            {"type": "message", "role": "assistant", "text": clean_msg}
                        )

                last_seen_index = current_len

            # STREAM AWAITING PROMPT DIRECTLY FROM SCHEMA (ONCE PER TOKEN)
            if token and token not in handled_tokens:
                handled_tokens.add(token)
                prompt_text = awaiting.get("prompt", "")
                clean_prompt = clean_text_pipes(prompt_text)
                if clean_prompt:
                    await websocket.send_json(
                        {"type": "message", "role": "assistant", "text": clean_prompt}
                    )

                options = get_options_from_state(session_state)
                await websocket.send_json({"type": "options", "options": options})

    poll_task = asyncio.create_task(stream_background_events())

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_msg = payload.get("message", "").strip()

            if not user_msg:
                continue

            prev_token = (
                session_state.get("awaiting", {}).get("token")
                if session_state and session_state.get("awaiting")
                else None
            )

            # Execute agent invocation
            agent_response = await agent_instance.respond(
                user_msg, context=session_state
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
                        {"type": "message", "role": "assistant", "text": clean_warning}
                    )

            options = get_options_from_state(session_state)
            await websocket.send_json({"type": "options", "options": options})

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    finally:
        poll_task.cancel()


def main() -> None:
    """Launch the chat UI."""
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
