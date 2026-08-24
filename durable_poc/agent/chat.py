"""Gradio chat interface for the workflow agent."""

from __future__ import annotations

import os
from typing import Any, Callable

import gradio as gr


def create_chat_fn(agent: Any) -> Callable[[str, list[Any]], str]:
    """Create the chat function that Gradio will call on each user message.

    Args:
        agent: A WorkflowAgent instance (or any object with a respond method).

    Returns:
        A function with signature (message, history) -> response.
    """

    def chat_fn(message: str, history: list[Any]) -> str:
        return agent.respond(message)

    return chat_fn


def create_app(agent: Any) -> gr.Blocks:
    """Create a Gradio ChatInterface app backed by the given agent.

    Args:
        agent: A WorkflowAgent instance.

    Returns:
        A Gradio Blocks app ready to launch.
    """
    chat_fn = create_chat_fn(agent)
    app = gr.ChatInterface(
        fn=chat_fn,
        title="DVLA Workflow Assistant",
        description="I can help you with government service workflows like changing the address on your driving licence.",
    )
    return app


async def main() -> None:
    """Connect to services and launch the chat UI."""
    import httpx
    from temporalio.client import Client

    from agent.agent import WorkflowAgent

    temporal_client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    )
    http_client = httpx.AsyncClient()

    agent = WorkflowAgent(
        temporal_client=temporal_client,
        http_client=http_client,
        workflow_server_url=os.environ.get("WORKFLOW_SERVER_URL", "http://localhost:8080"),
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
    )

    app = create_app(agent)
    app.launch()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
