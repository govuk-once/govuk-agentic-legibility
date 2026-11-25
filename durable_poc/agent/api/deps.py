"""Shared clients and settings for the durable_poc API.

Mirrors `agent/chat.py`'s module-level `_get_polling_client()`: one
process-wide, untraced Temporal client for REST/SSE reads, kept separate
from the per-connection `TracingInterceptor`-wrapped client each
`WorkflowAgent` opens for itself.
"""

from __future__ import annotations

import os

import httpx
from strands.models.model import Model
from temporalio.client import Client as TemporalClient

from agent.agent import WorkflowAgent

_polling_client: TemporalClient | None = None
_http_client: httpx.AsyncClient | None = None


def temporal_address() -> str:
    """Temporal frontend address, e.g. `localhost:7233`."""
    return os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


def workflow_server_url() -> str:
    """Base URL of the workflow definition server."""
    return os.environ.get("WORKFLOW_SERVER_URL", "http://localhost:8080")


def task_queue() -> str:
    """Temporal task queue the SFSM interpreter worker polls."""
    return os.environ.get("TEMPORAL_TASK_QUEUE", "sfsm-queue")


async def get_polling_client() -> TemporalClient:
    """Return the process-wide, untraced Temporal client used for reads.

    FastAPI dependency — call directly (not via `Depends`) from code that
    isn't a route handler, such as a WebSocket route's background task.
    """
    global _polling_client
    if _polling_client is None:
        _polling_client = await TemporalClient.connect(temporal_address())
    return _polling_client


async def get_http_client() -> httpx.AsyncClient:
    """Return the process-wide httpx client used to reach the workflow server."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


def _dev_model_override() -> Model | None:
    """Local/dev escape hatch: route the agent through OpenRouter instead of
    Bedrock when `OPENROUTER_API_KEY` is set — e.g. machines without AWS
    credentials. Unset in any environment that should use Bedrock (the
    intended production path); this is never selected automatically there.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"},
        model_id=os.environ.get("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4.5"),
        params={"temperature": 0.0},
    )


def new_workflow_agent() -> WorkflowAgent:
    """Build one traced `WorkflowAgent` for a single chat/voice connection."""
    return WorkflowAgent(
        workflow_server_url=workflow_server_url(),
        model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
        temporal_address=temporal_address(),
        task_queue=task_queue(),
        model=_dev_model_override(),
    )


def new_agentic_agent(
    *, conversation_history: list[dict] | None = None
) -> WorkflowAgent:
    """Build a `WorkflowAgent` for the `/agentic` autonomous answerer, with the
    `escalate_to_human` tool enabled.

    This is the one route besides chat/voice allowed to let the agent decide a
    value — an explicitly scoped exception to the Dual-Path guarantee, made
    auditable by `agent/api/routes/agentic.py` tagging every autonomous
    `submit_input` with its provenance.
    """
    return WorkflowAgent(
        workflow_server_url=workflow_server_url(),
        model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
        temporal_address=temporal_address(),
        task_queue=task_queue(),
        model=_dev_model_override(),
        conversation_history=conversation_history,
        enable_escalation=True,
    )


async def shutdown() -> None:
    """Release process-wide clients on app shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
