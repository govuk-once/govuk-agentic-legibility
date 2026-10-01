"""`create_app()` factory for the durable_poc HTTP+WS+SSE service.

Replaces `agent/chat.py`'s embedded-HTML FastAPI app as the thing the
various downstream frontends such as `durable-frontend/` talk to. 
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from agent.api import deps
from agent.api.routes import agentic, chat_ws, runs, workflows
from src.telemetry import SessionSpanProcessor, create_agent_provider

# Origins must be replaced before deployment
DEFAULT_FRONTEND_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await deps.shutdown()


def create_app() -> FastAPI:
    """Build the generalized durable_poc API.

    Mounts the workflow-catalogue, run-lifecycle, and chat-WS routers, and
    wires up the same session-scoped tracer provider `chat.py:main()`
    configures today.

    Returns:
        Configured FastAPI application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    session_processor = SessionSpanProcessor()
    trace.set_tracer_provider(create_agent_provider(session_processor=session_processor))

    app = FastAPI(title="GOV.UK Durable Workflow API", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEFAULT_FRONTEND_ORIGINS),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthcheck")
    def healthcheck() -> dict[str, str]:
        """Return a simple process health response."""
        return {"status": "ok"}

    app.include_router(workflows.router)
    app.include_router(runs.router)
    app.include_router(agentic.router)
    app.include_router(chat_ws.router)

    return app
