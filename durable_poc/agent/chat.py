"""Gradio chat interface for the workflow agent."""

from __future__ import annotations

import logging
import os
import mimetypes
from typing import Any, AsyncGenerator, Callable

import gradio as gr

logger = logging.getLogger(__name__)


def get_options_from_state(state: dict[str, Any] | None) -> list[str]:
    """Extract human-readable options generically from current awaiting schema in session state."""
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


def build_file_payload(file_obj: Any) -> str:
    """Format uploaded file info into a JSON-like text message for the agent."""
    file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "image/jpeg"
    
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # Formats reference cleanly so agent can map to file_ref schema
    return (
        f"[Uploaded File: "
        f"content_type='{content_type}', bytes={file_size}]"
    )


def create_chat_fn(
    agent: Any,
) -> Callable[[str, list[Any], dict[str, Any] | None], Any]:
    """Create the chat function that Gradio will call on each user message.

    The function follows the HATEOAS pattern: the agent's session_state
    (workflow_id + awaiting) is read before each turn to provide context,
    and read again after to capture updates from tool calls.

    Args:
        agent: A WorkflowAgent instance (or any object with respond/session_state).

    Returns:
        An async function with signature (message, history, state) -> (response, state).
    """

    async def chat_fn(
        message: str, history: list[Any], state: dict[str, Any] | None
    ) -> tuple[str, dict[str, Any] | None]:
        context = state if state is not None else getattr(agent, "session_state", None)
        logger.info(
            "Chat turn: message=%r has_context=%s",
            message[:80],
            bool(context),
        )
        try:
            response = await agent.respond(message, context=context)
        except Exception:
            logger.exception("Agent failed to respond to message: %r", message[:80])
            return (
                "I'm sorry, an unexpected error occurred. Please try again.",
                state,
            )
        new_state = getattr(agent, "session_state", None)
        logger.info(
            "Chat turn complete: response_length=%d state_changed=%s",
            len(response),
            new_state != state,
        )
        return response, new_state

    return chat_fn


def create_app(agent: Any) -> gr.Blocks:
    """Create a Gradio chat app backed by the given agent.

    Args:
        agent: A WorkflowAgent instance.

    Returns:
        A Gradio Blocks app ready to launch.
    """
    chat_fn = create_chat_fn(agent)

    with gr.Blocks(title="GOV.UK Chat Assistant") as app:
        gr.Markdown("# GOV.UK Chat Assistant")
        gr.Markdown(
            "I can help you with government services like "
            "changing the address on your driving licence."
        )
        chatbot = gr.Chatbot()
        session_state = gr.State(value=None)

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Type a message or select an option below...",
                show_label=False,
                scale=3,
            )
            file_upload = gr.File(
                label="Upload Photo",
                file_types=["image"],
                type="filepath",
                scale=1,
            )
            send_btn = gr.Button("Send", scale=1)

        choice_dataset = gr.Dataset(
            components=[gr.Textbox(visible=False)],
            label="Available Options",
            samples=[],
            visible=False,
        )

        async def respond(
            message: str, file_obj: Any, history: list[Any], state: dict[str, Any] | None
        ) -> AsyncGenerator[tuple[str, None, list[Any], dict[str, Any] | None, dict[str, Any]], None]:
            
            # Combine text and file upload inputs
            user_payload = message or ""
            if file_obj is not None:
                file_info = build_file_payload(file_obj)
                user_payload = f"{user_payload} {file_info}".strip()

            if not user_payload:
                yield "", None, history, state, gr.update()
                return

            updated_history = history + [{"role": "user", "content": user_payload}]
            yield "", None, updated_history, state, gr.update()

            response, new_state = await chat_fn(user_payload, history, state)

            final_history = updated_history + [
                {"role": "assistant", "content": response}
            ]

            options = get_options_from_state(new_state)
            samples = [[opt] for opt in options]
            dataset_update = gr.update(samples=samples, visible=bool(options))

            yield "", None, final_history, new_state, dataset_update

        # Handlers for text submit & button click
        msg.submit(
            respond,
            [msg, file_upload, chatbot, session_state],
            [msg, file_upload, chatbot, session_state, choice_dataset],
        )
        send_btn.click(
            respond,
            [msg, file_upload, chatbot, session_state],
            [msg, file_upload, chatbot, session_state, choice_dataset],
        )

        # Dataset option select handler
        async def on_select_option(
            evt_data: gr.SelectData, history: list[Any], state: dict[str, Any] | None
        ) -> AsyncGenerator[tuple[str, None, list[Any], dict[str, Any] | None, dict[str, Any]], None]:
            val = evt_data.value
            selected_value = val[0] if isinstance(val, (list, tuple)) else str(val)
            async for update in respond(selected_value, None, history, state):
                yield update

        choice_dataset.select(
            on_select_option,
            inputs=[chatbot, session_state],
            outputs=[msg, file_upload, chatbot, session_state, choice_dataset],
        )

    return app


def main() -> None:
    """Launch the chat UI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    from agent.agent import WorkflowAgent

    workflow_server_url = os.environ.get(
        "WORKFLOW_SERVER_URL", "http://localhost:8080"
    )
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")
    region_name = os.environ.get("AWS_REGION", "eu-west-2")
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

    logger.info(
        "Starting chat UI: workflow_server=%s model=%s region=%s temporal=%s",
        workflow_server_url,
        model_id,
        region_name,
        temporal_address,
    )

    agent = WorkflowAgent(
        workflow_server_url=workflow_server_url,
        model_id=model_id,
        region_name=region_name,
        temporal_address=temporal_address,
    )

    app = create_app(agent)
    app.launch()


if __name__ == "__main__":
    main()
