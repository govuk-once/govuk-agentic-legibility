"""Workflow catalogue routes: list and fetch definitions from the workflow server.

Thin wrappers over `agent.tools` — no Temporal involvement, no agent
involvement. Used by `/web` and `/agentic` to populate a "start a new run"
picker, and by `/chat`'s resume flow.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from agent import tools as tool_functions
from agent.api import deps

router = APIRouter(prefix="/api/v1", tags=["workflows"])


@router.get("/workflows")
async def list_workflows(
    http_client: httpx.AsyncClient = Depends(deps.get_http_client),
) -> list[dict[str, Any]]:
    """List all workflow definitions registered on the workflow server."""
    try:
        return await tool_functions.list_available_workflows(
            http_client=http_client, base_url=deps.workflow_server_url()
        )
    except tool_functions.WorkflowServerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    http_client: httpx.AsyncClient = Depends(deps.get_http_client),
) -> dict[str, Any]:
    """Fetch one workflow definition by ID or slug."""
    try:
        return await tool_functions.get_workflow_definition(
            workflow_id=workflow_id,
            http_client=http_client,
            base_url=deps.workflow_server_url(),
        )
    except tool_functions.WorkflowServerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
