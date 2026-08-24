"""Tool functions that bridge the agent to Temporal and the workflow server."""

from __future__ import annotations

from typing import Any

import httpx


class WorkflowServerError(Exception):
    """Raised when the workflow definition server returns an error."""


async def get_workflow_definition(
    *,
    workflow_id: int,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """Fetch a workflow definition from the workflow server.

    Args:
        workflow_id: Numeric ID of the workflow to retrieve.
        http_client: An httpx async client instance.
        base_url: Base URL of the workflow server.

    Returns:
        The parsed workflow definition dict.

    Raises:
        WorkflowServerError: If the server returns a non-2xx response.
    """
    url = f"{base_url}/api/v1/workflows/{workflow_id}"
    response = await http_client.get(url)
    if response.status_code >= 400:
        raise WorkflowServerError(
            f"Workflow server returned {response.status_code} for workflow {workflow_id}"
        )
    return response.json()


async def start_workflow(
    *,
    definition: dict[str, Any],
    temporal_client: Any,
    task_queue: str,
) -> str:
    """Start a workflow execution on Temporal.

    Args:
        definition: The FSM workflow definition dict.
        temporal_client: A Temporal client instance.
        task_queue: The Temporal task queue to use.

    Returns:
        The Temporal workflow ID for the started execution.
    """
    handle = await temporal_client.start_workflow(
        "SFSMInterpreter",
        arg=definition,
        id=f"sfsm-{definition.get('id', 'unknown')}-{definition.get('version', '0')}",
        task_queue=task_queue,
    )
    return handle.id


async def get_workflow_state(
    *,
    workflow_id: str,
    temporal_client: Any,
) -> dict[str, Any]:
    """Query workflow state from Temporal. Implementation pending."""
    raise NotImplementedError


async def submit_input(
    *,
    workflow_id: str,
    token: str,
    value: Any,
    temporal_client: Any,
) -> None:
    """Submit input to a running workflow. Implementation pending."""
    raise NotImplementedError
