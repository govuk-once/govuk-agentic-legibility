"""Gradio chat interface for the workflow agent."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

import gradio as gr

logger = logging.getLogger(__name__)


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

    with gr.Blocks(title="Workflow Assistant") as app:
        gr.Markdown("# Workflow Assistant")
        gr.Markdown(
            "I can help you with government service workflows like "
            "changing the address on your driving licence."
        )
        chatbot = gr.Chatbot()
        session_state = gr.State(value=None)
        msg = gr.Textbox(placeholder="Type a message...", show_label=False)

        async def respond(
            message: str, history: list[Any], state: dict[str, Any] | None
        ) -> tuple[str, list[Any], dict[str, Any] | None]:
            response, new_state = await chat_fn(message, history, state)
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]
            return "", history, new_state

        msg.submit(respond, [msg, chatbot, session_state], [msg, chatbot, session_state])

    return app


def main() -> None:
    """Launch the chat UI. Temporal connects lazily on first tool call."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    from agent.agent import WorkflowAgent

    workflow_server_url = os.environ.get("WORKFLOW_SERVER_URL", "http://localhost:8080")
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
