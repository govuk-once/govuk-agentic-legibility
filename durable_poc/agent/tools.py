"""
Tool functions that bridge the agent to:

- Workflow Server (SFSM)
- Local BPMN workflows
- Temporal runtime
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import logging
from typing import Any
import uuid

import httpx

from src.context import InputSubmission
from bpmn.temporal_engine.process_registry import PROCESS_REGISTRY

logger = logging.getLogger(__name__)

WORKFLOW_NAME = "BPMNInterpreter"


class WorkflowServerError(Exception):
    """Raised when the workflow definition server returns an error."""


def _to_dict(obj: Any) -> Any:
    """
    Recursively convert dataclasses and custom objects
    into plain dictionaries.
    """

    if obj is None:
        return None

    if isinstance(obj, dict):
        return {
            k: _to_dict(v)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [
            _to_dict(item)
            for item in obj
        ]

    if is_dataclass(obj):
        return asdict(obj)

    if hasattr(obj, "__dict__"):
        return {
            k: _to_dict(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }

    return obj


# ---------------------------------------------------------------------
# Workflow Server (SFSM)
# ---------------------------------------------------------------------


async def list_available_workflows(
    *,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> list[dict[str, Any]]:
    """
    Fetch all registered workflow definitions.
    """

    url = f"{base_url}/api/v1/workflows"

    logger.info(
        "Listing registered workflow definitions: GET %s",
        url,
    )

    response = await http_client.get(url)

    response.raise_for_status()

    workflows = response.json()["workflows"]

    logger.info(
        "Retrieved %d workflow definition(s)",
        len(workflows),
    )

    return workflows


async def find_workflow_by_intent(
    domain_keyword: str,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """
    Find a workflow matching a keyword.
    """

    workflows = await list_available_workflows(
        http_client=http_client,
        base_url=base_url,
    )

    keyword = domain_keyword.strip().lower()

    for workflow in workflows:

        workflow_slug = str(
            workflow.get("id", "")
        ).lower()

        workflow_version = str(
            workflow.get("version", "")
        ).lower()

        searchable = " ".join(
            [
                workflow_slug,
                workflow_version,
            ]
        )

        logger.info(
            "Checking workflow_id=%s slug=%s keyword=%s",
            workflow.get("workflow_id"),
            workflow_slug,
            keyword,
        )

        if keyword in searchable:

            return await get_workflow_definition(
                workflow_id=workflow["workflow_id"],
                http_client=http_client,
                base_url=base_url,
            )

    raise ValueError(
        f"No workflow found matching keyword '{domain_keyword}'"
    )


async def get_workflow_definition(
    *,
    workflow_id: int | str,
    http_client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """
    Fetch a workflow definition from the workflow server.
    """

    url = f"{base_url}/api/v1/workflows/{workflow_id}"

    logger.info(
        "Fetching workflow definition: GET %s",
        url,
    )

    response = await http_client.get(url)

    response.raise_for_status()

    definition = response.json()

    logger.info(
        "Fetched workflow definition: id=%s version=%s",
        definition.get("id"),
        definition.get("version"),
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
    """
    Existing SFSM workflow startup path.

    Retained for backwards compatibility.
    """

    definition = await get_workflow_definition(
        workflow_id=workflow_id,
        http_client=http_client,
        base_url=base_url,
    )

    unique_suffix = str(
        uuid.uuid4()
    )[:8]

    temporal_id = (
        f"{definition.get('id', 'workflow')}-"
        f"{unique_suffix}"
    )

    logger.info(
        "Starting workflow on Temporal: id=%s task_queue=%s",
        temporal_id,
        task_queue,
    )

    handle = await temporal_client.start_workflow(
        definition,
        id=temporal_id,
        task_queue=task_queue,
    )

    logger.info(
        "Workflow started: %s",
        handle.id,
    )

    return handle.id


# ---------------------------------------------------------------------
# BPMN
# ---------------------------------------------------------------------


async def list_bpmn_workflows() -> list[dict[str, str]]:
    """
    List BPMN workflows available through the process registry.
    """

    logger.info(
        "Listing BPMN workflows"
    )

    return [
        {
            "id": process_id,
            "path": process_path,
        }
        for process_id, process_path
        in PROCESS_REGISTRY.items()
    ]


async def start_bpmn_workflow(
    *,
    process_id: str,
    temporal_client: Any,
    task_queue: str,
) -> str:
    """
    Start a BPMN workflow using the process registry.
    """

    if process_id not in PROCESS_REGISTRY:
        raise ValueError(
            f"Unknown BPMN process '{process_id}'"
        )

    unique_suffix = str(
        uuid.uuid4()
    )[:8]

    workflow_id = (
        f"bpmninterpreter-"
        f"{process_id}-"
        f"{unique_suffix}"
    )

    logger.info(
        "Starting BPMN workflow "
        "process_id=%s "
        "workflow_id=%s "
        "task_queue=%s",
        process_id,
        workflow_id,
        task_queue,
    )

    handle = await temporal_client.start_workflow(
        WORKFLOW_NAME,
        arg={
            "process_id": process_id,
        },
        id=workflow_id,
        task_queue=task_queue,
    )

    logger.info(
        "Workflow started: %s",
        handle.id,
    )

    return handle.id


# ---------------------------------------------------------------------
# Shared Runtime Functions
# ---------------------------------------------------------------------


async def list_active_workflows(
    *,
    temporal_client: Any,
) -> list[dict[str, str]]:
    """
    List active workflow executions.
    """

    logger.info(
        "Listing active workflows"
    )

    results: list[dict[str, str]] = []

    async for execution in temporal_client.list_workflows():

        results.append(
            {
                "id": execution.id,
                "status": str(execution.status),
            }
        )

    logger.info(
        "Found %d active workflow(s)",
        len(results),
    )

    return results


async def get_workflow_state(
    *,
    workflow_id: str,
    temporal_client: Any,
) -> dict[str, Any]:
    """
    Query workflow state.
    """

    logger.info(
        "Querying workflow state: %s",
        workflow_id,
    )

    handle = temporal_client.get_workflow_handle(
        workflow_id,
    )

    description = await handle.describe()

    status_name = (
        description.status.name
        if description.status
        else "RUNNING"
    )

    raw_awaiting = await handle.query(
        "awaiting"
    )

    raw_transcript = await handle.query(
        "transcript"
    )

    awaiting = _to_dict(
        raw_awaiting
    )

    transcript = _to_dict(
        raw_transcript
    )

    if awaiting:
        logger.info(
            "Workflow %s awaiting input token=%s",
            workflow_id,
            awaiting.get("token"),
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
    """
    Submit user input.
    """

    logger.info(
        "Submitting input workflow=%s token=%s value=%r",
        workflow_id,
        token,
        value,
    )

    handle = temporal_client.get_workflow_handle(
        workflow_id,
    )

    await handle.execute_update(
        "submit_input",
        InputSubmission(
            token=token,
            value=value,
        ),
    )

    return await get_workflow_state(
        workflow_id=workflow_id,
        temporal_client=temporal_client,
    )