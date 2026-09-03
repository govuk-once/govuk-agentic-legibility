"""Tool functions that bridge the agent to Temporal and the workflow server."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import logging
from typing import Any
import uuid

import httpx

from src.context import InputSubmission

logger = logging.getLogger(__name__)


class WorkflowServerError(Exception):
    """Raised when the workflow definition server returns an error."""


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses or custom objects to plain dictionaries."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return {
            k: _to_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")
        }
    return obj


async def list_available_workflows(
    *,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> list[dict[str, Any]]:
    """Fetch all registered workflow definitions from the server."""
    url = f"{base_url}/api/v1/workflows"
    logger.info("Listing registered workflow definitions: GET %s", url)
    try:
        response = await http_client.get(url)
    except httpx.RequestError as e:
        logger.error("Failed to fetch registered workflows: %s", e)
        raise WorkflowServerError(f"Failed to connect to workflow server: {e}") from e
    if response.status_code >= 400:
        raise WorkflowServerError(
            f"Workflow server returned {response.status_code} while listing workflows"
        )
    workflows = response.json()
    logger.info("Retrieved %d workflow definition(s) from server", len(workflows))
    return workflows


async def find_workflow_by_intent(
    *,
    domain_keyword: str,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """Find a workflow definition matching a specific user domain or keyword (e.g. 'maternity', 'address')."""
    workflows = await list_available_workflows(
        http_client=http_client, base_url=base_url
    )
    keyword = domain_keyword.lower().strip()

    for wf in workflows:
        wf_id = str(wf.get("id", "")).lower()
        wf_name = str(wf.get("name", "")).lower()
        if keyword in wf_id or keyword in wf_name:
            logger.info("Matched workflow '%s' for keyword '%s'", wf.get("id"), domain_keyword)
            return wf

    logger.warning("No workflow found matching keyword '%s'", domain_keyword)
    return {
        "error": f"No registered workflow found matching keyword '{domain_keyword}'",
        "available_workflows": [w.get("id") for w in workflows],
    }


async def get_workflow_definition(
    *,
    workflow_id: int | str,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """Fetch a workflow definition from the workflow server by numeric ID or string slug."""
    # If a string identifier is supplied, resolve via lookup
    if isinstance(workflow_id, str) and not workflow_id.isdigit():
        found = await find_workflow_by_intent(
            domain_keyword=workflow_id, http_client=http_client, base_url=base_url
        )
        if "error" in found:
            raise WorkflowServerError(found["error"])
        return found

    url = f"{base_url}/api/v1/workflows/{workflow_id}"
    logger.info("Fetching workflow definition: GET %s", url)
    try:
        response = await http_client.get(url)
    except httpx.RequestError as e:
        logger.error("HTTP request failed for workflow %s: %s", workflow_id, e)
        raise WorkflowServerError(f"Failed to connect to workflow server: {e}") from e
    if response.status_code >= 400:
        logger.error(
            "Workflow server returned %d for workflow %s: %s",
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
    workflow_id: int | str,
    http_client: httpx.AsyncClient,
    base_url: str,
    temporal_client: Any,
    task_queue: str,
) -> str:
    """Fetch a workflow definition and start it on Temporal."""
    definition = await get_workflow_definition(
        workflow_id=workflow_id, http_client=http_client, base_url=base_url
    )

    # Append unique execution token to prevent duplicate workflow ID errors
    unique_suffix = str(uuid.uuid4())[:8]
    temporal_id = f"sfsm-{definition.get('id', 'unknown')}-{unique_suffix}"

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
            results.append({"id": execution.id, "status": str(execution.status)})
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
        description = await handle.describe()
        status_name = description.status.name if description.status else "RUNNING"

        raw_awaiting = await handle.query("awaiting")
        raw_transcript = await handle.query("transcript")
    except Exception:
        logger.exception("Failed to query state for workflow %s", workflow_id)
        raise

    # Safely convert dataclasses to standard dictionary representations
    awaiting = _to_dict(raw_awaiting)
    transcript = _to_dict(raw_transcript)

    if awaiting:
        logger.info(
            "Workflow %s awaiting input: token=%s prompt=%r",
            workflow_id,
            awaiting.get("token"),
            awaiting.get("prompt"),
        )
    else:
        logger.info(
            "Workflow %s not awaiting input (status=%s)", workflow_id, status_name
        )

    return {
        "workflow_id": workflow_id,
        "status": status_name,
        "awaiting": awaiting,
        "transcript": transcript,
    }


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