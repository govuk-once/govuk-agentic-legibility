"""Tool functions that bridge the agent to Temporal and the workflow server."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.context import InputSubmission

logger = logging.getLogger(__name__)


class WorkflowServerError(Exception):
    """Raised when the workflow definition server returns an error."""


async def get_workflow_definition(
    *,
    workflow_id: int,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """Fetch a workflow definition from the workflow server."""
    url = f"{base_url}/api/v1/workflows/{workflow_id}"
    logger.info("Fetching workflow definition: GET %s", url)
    try:
        response = await http_client.get(url)
    except httpx.RequestError as e:
        logger.error("HTTP request failed for workflow %d: %s", workflow_id, e)
        raise WorkflowServerError(
            f"Failed to connect to workflow server: {e}"
        ) from e
    if response.status_code >= 400:
        logger.error(
            "Workflow server returned %d for workflow %d: %s",
            response.status_code,
            workflow_id,
            response.text[:200],
        )
        raise WorkflowServerError(
            f"Workflow server returned {response.status_code} for workflow {workflow_id}"
        )
    definition = response.json()
    logger.info(
        "Fetched workflow definition: id=%s version=%s",
        definition.get("id", "?"),
        definition.get("version", "?"),
    )
    return definition


async def start_workflow(
    *,
    workflow_id: int,
    http_client: httpx.AsyncClient,
    base_url: str,
    temporal_client: Any,
    task_queue: str,
) -> str:
    """Fetch a workflow definition and start it on Temporal."""
    definition = await get_workflow_definition(
        workflow_id=workflow_id, http_client=http_client, base_url=base_url
    )
    temporal_id = f"sfsm-{definition.get('id', 'unknown')}-{definition.get('version', '0')}"
    logger.info(
        "Starting workflow on Temporal: id=%s task_queue=%s",
        temporal_id,
        task_queue,
    )
    try:
        handle = await temporal_client.start_workflow(
            "SFSMInterpreter",
            arg=definition,
            id=temporal_id,
            task_queue=task_queue,
        )
    except Exception:
        logger.exception("Failed to start workflow %s on Temporal", temporal_id)
        raise
    logger.info("Workflow started: %s", handle.id)
    return handle.id


async def list_active_workflows(
    *,
    temporal_client: Any,
) -> list[dict[str, str]]:
    """List running SFSMInterpreter workflows on Temporal."""
    logger.info("Listing active workflows")
    try:
        results: list[dict[str, str]] = []
        async for execution in temporal_client.list_workflows(
            "WorkflowType = 'SFSMInterpreter' AND ExecutionStatus = 'Running'"
        ):
            results.append({"id": execution.id, "status": execution.status})
    except Exception:
        logger.exception("Failed to list workflows from Temporal")
        raise
    logger.info("Found %d active workflow(s)", len(results))
    return results


async def get_workflow_state(
    *,
    workflow_id: str,
    temporal_client: Any,
) -> dict[str, Any]:
    """Query the current state of a running workflow."""
    logger.info("Querying workflow state: %s", workflow_id)
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        awaiting = await handle.query("awaiting")
        transcript = await handle.query("transcript")
    except Exception:
        logger.exception("Failed to query state for workflow %s", workflow_id)
        raise
    if awaiting:
        logger.info(
            "Workflow %s awaiting input: token=%s prompt=%r",
            workflow_id,
            awaiting.get("token") if isinstance(awaiting, dict) else getattr(awaiting, "token", "?"),
            awaiting.get("prompt") if isinstance(awaiting, dict) else getattr(awaiting, "prompt", "?"),
        )
    else:
        logger.info("Workflow %s not awaiting input (processing or completed)", workflow_id)
    return {"awaiting": awaiting, "transcript": transcript}


async def submit_input(
    *,
    workflow_id: str,
    token: str,
    value: Any,
    temporal_client: Any,
) -> dict[str, Any]:
    """Submit user input and return the new workflow state."""
    logger.info(
        "Submitting input to workflow %s: token=%s value=%r (type=%s)",
        workflow_id,
        token,
        value,
        type(value).__name__,
    )
    handle = temporal_client.get_workflow_handle(workflow_id)
    try:
        await handle.execute_update(
            "submit_input", InputSubmission(token=token, value=value)
        )
    except Exception:
        logger.exception(
            "Workflow %s rejected input: token=%s value=%r",
            workflow_id,
            token,
            value,
        )
        raise
    logger.info("Input accepted by workflow %s, querying new state", workflow_id)
    return await get_workflow_state(
        workflow_id=workflow_id, temporal_client=temporal_client
    )
