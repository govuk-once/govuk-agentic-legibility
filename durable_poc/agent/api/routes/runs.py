"""Run lifecycle routes: start, inspect, submit input, and stream state diffs.

The LLM-free surface: only `agent.tools` and `events.watch_run` are
imported here, never `agent.agent.WorkflowAgent`. This is what `/web`
drives end to end, and what `/agentic` uses for its deterministic reads
(starting/inspecting runs, submitting escalated fields) alongside its own
autonomy routes.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from temporalio.client import Client as TemporalClient

from agent import tools as tool_functions
from agent.api import deps
from agent.api.events import watch_run
from agent.api.schemas import InputSubmissionRequest, StartRunRequest, StartRunResponse

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post("/runs", status_code=201, response_model=StartRunResponse)
async def start_run(
    request: StartRunRequest,
    http_client: httpx.AsyncClient = Depends(deps.get_http_client),
    temporal_client: TemporalClient = Depends(deps.get_polling_client),
) -> StartRunResponse:
    """Fetch a workflow definition and start it as a new Temporal execution."""
    try:
        workflow_id = await tool_functions.start_workflow(
            workflow_id=request.workflow_id,
            http_client=http_client,
            base_url=deps.workflow_server_url(),
            temporal_client=temporal_client,
            task_queue=deps.task_queue(),
        )
    except tool_functions.WorkflowServerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return StartRunResponse(workflow_id=workflow_id)


@router.get("/runs")
async def list_runs(
    temporal_client: TemporalClient = Depends(deps.get_polling_client),
) -> list[dict[str, str]]:
    """List currently-running SFSM executions (used by `/agentic` and resume pickers)."""
    return await tool_functions.list_active_workflows(temporal_client=temporal_client)


@router.get("/runs/{workflow_id}")
async def get_run(
    workflow_id: str,
    temporal_client: TemporalClient = Depends(deps.get_polling_client),
) -> dict[str, Any]:
    """Return the current state (status, awaiting field, transcript) of one run."""
    try:
        return await tool_functions.get_workflow_state(
            workflow_id=workflow_id, temporal_client=temporal_client
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Run not found: {workflow_id}"
        ) from exc


@router.post("/runs/{workflow_id}/input")
async def submit_run_input(
    workflow_id: str,
    request: InputSubmissionRequest,
    temporal_client: TemporalClient = Depends(deps.get_polling_client),
) -> dict[str, Any]:
    """Submit a value for the field the run is currently awaiting."""
    try:
        return await tool_functions.submit_input(
            workflow_id=workflow_id,
            token=request.token,
            value=request.value,
            temporal_client=temporal_client,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs/{workflow_id}/events")
async def run_events(
    workflow_id: str,
    temporal_client: TemporalClient = Depends(deps.get_polling_client),
) -> StreamingResponse:
    """Server-sent events: transcript lines, awaiting-field options/timeout,
    engine trace entries, and a final `completed` event."""

    async def event_stream() -> AsyncIterator[str]:
        async for event in watch_run(workflow_id, temporal_client):
            yield f"data: {json.dumps(event.to_dict())}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
