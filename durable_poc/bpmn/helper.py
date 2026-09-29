"""
Utility functions for generic BPMN workflow execution.

This module contains helper functions used by the workflow runner
to:

* Extract metadata from BPMN task definitions.
* Resolve and interpolate workflow variables.
* Identify executable workflow tasks.
* Log workflow state and data for debugging.
* Process file inputs supplied by users.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
from typing import Any

from SpiffWorkflow.task import TaskState

logger = logging.getLogger(__name__)


def get_task_id(task: Any) -> str:
    """
    Return a stable identifier for a workflow task.

    The function attempts to determine the most useful identifier
    available from the underlying task specification, prioritising
    BPMN identifiers when present.

    Args:
        task:
            A SpiffWorkflow task instance.

    Returns:
        A string identifier that can be used for logging,
        debugging, and task comparisons.
    """
    spec = task.task_spec

    return (
        getattr(spec, "bpmn_id", None)
        or getattr(spec, "id", None)
        or getattr(spec, "name", None)
        or str(spec)
    )


def get_metadata(task: Any) -> dict[str, Any]:
    """
    Parse workflow metadata from a task's documentation field.

    BPMN task documentation is expected to contain a JSON object
    describing task behaviour, forms, service endpoints,
    validation rules, or other configuration values.

    Args:
        task:
            A SpiffWorkflow task instance.

    Returns:
        A dictionary containing the parsed metadata.

        Returns an empty dictionary when no documentation exists
        or when the metadata cannot be parsed.
    """
    documentation = getattr(
        task.task_spec,
        "documentation",
        None,
    )

    if not documentation:
        return {}

    try:
        return json.loads(documentation.strip())

    except json.JSONDecodeError:
        logger.exception(
            "Failed to parse metadata for task %s",
            getattr(task.task_spec, "name", "<unknown>"),
        )
        return {}


def get_value(
    data: dict[str, Any],
    path: str,
) -> Any:
    """
    Resolve a value from workflow data using dot notation.

    For example:

        get_value(data, "applicant.name")

    resolves:

        data["applicant"]["name"]

    Args:
        data:
            Workflow data dictionary.

        path:
            Dot-separated path to resolve.

    Returns:
        The resolved value.

    Raises:
        KeyError:
            Raised when any component of the path cannot
            be resolved.
    """
    current: Any = data

    for part in path.split("."):
        if not isinstance(current, dict):
            raise KeyError(f"Cannot resolve '{path}'. '{part}' is not a dictionary.")

        if part not in current:
            raise KeyError(f"Cannot resolve '{path}'. Missing key '{part}'.")

        current = current[part]

    return current


def interpolate_string(
    value: str,
    data: dict[str, Any],
) -> str:
    """
    Replace variable placeholders within a string.

    Placeholders use the form:

        ${variable}
        ${applicant.name}

    Each placeholder is resolved against workflow data and
    substituted with its corresponding value.

    Args:
        value:
            String containing placeholders.

        data:
            Workflow data available to the current process.

    Returns:
        The interpolated string.
    """
    matches = re.findall(
        r"\$\{([^}]+)\}",
        value,
    )

    result = value

    for match in matches:
        replacement = get_value(
            data,
            match,
        )

        if replacement is None:
            replacement = ""

        result = result.replace(
            f"${{{match}}}",
            str(replacement),
        )

    return result


def interpolate_object(
    obj: Any,
    data: dict[str, Any],
) -> Any:
    """
    Recursively interpolate variables within an object.

    Strings are processed for variable substitutions while
    lists and dictionaries are traversed recursively.
    Primitive values are returned unchanged.

    Args:
        obj:
            Object to interpolate.

        data:
            Workflow data used for variable resolution.

    Returns:
        A new object with all variable references resolved.
    """
    if isinstance(obj, str):
        return interpolate_string(
            obj,
            data,
        )

    if isinstance(obj, list):
        return [
            interpolate_object(
                item,
                data,
            )
            for item in obj
        ]

    if isinstance(obj, dict):
        return {
            key: interpolate_object(
                value,
                data,
            )
            for key, value in obj.items()
        }

    return obj


def get_executable_tasks(
    workflow: Any,
) -> list[Any]:
    """
    Retrieve tasks that are ready for execution.

    A task is considered executable when it is in either
    the READY or STARTED state.

    Args:
        workflow:
            Active workflow instance.

    Returns:
        A list containing executable workflow tasks.

    Raises:
        Exception:
            Re-raises any exception encountered while
            inspecting workflow state.
    """

    executable = []

    try:
        for task in workflow.get_tasks():
            if task.has_state(TaskState.READY) or task.has_state(TaskState.STARTED):
                logger.debug(
                    "Executable task: %s (%s)",
                    task.task_spec.name,
                    TaskState.get_name(task.state),
                )

                executable.append(task)

    except Exception:
        logger.exception("Failed to determine executable tasks")
        raise

    return executable


def dump_tasks(
    workflow: Any,
) -> None:
    """
    Log the current workflow task state.

    This function outputs task information such as task name,
    task type, and current state. It is intended primarily for
    diagnostics and troubleshooting.

    Args:
        workflow:
            Active workflow instance.
    """
    try:
        logger.debug("Current Tasks")
        logger.debug("-------------")

        for task in workflow.get_tasks():
            logger.debug(
                "%-35s%-30s%s",
                task.task_spec.name,
                task.task_spec.__class__.__name__,
                TaskState.get_name(task.state),
            )

    except Exception:
        logger.exception("Failed to dump workflow tasks")


def dump_data(
    workflow: Any,
) -> None:
    """
    Log workflow data currently stored in the process.

    This function is intended for debugging and provides a
    snapshot of workflow variables at runtime.

    Args:
        workflow:
            Active workflow instance.
    """
    try:
        logger.debug("Workflow Data")
        logger.debug("-------------")

        data: dict[str, Any] = getattr(
            workflow,
            "data",
            {},
        )

        for key, value in data.items():
            logger.debug(
                "%s: %s",
                key,
                value,
            )

    except Exception:
        logger.exception("Failed to dump workflow data")


def process_file_field(
    path: str,
) -> dict[str, Any]:
    """
    Generate metadata for a user-supplied file.

    The file is validated and converted into a structured
    dictionary that can be stored in workflow data or passed
    to downstream service tasks.

    Args:
        path:
            File path provided by the user.

    Returns:
        Dictionary containing file metadata including:

        * path
        * filename
        * content_type
        * bytes

    Raises:
        FileNotFoundError:
            Raised when the specified file does not exist.

        ValueError:
            Raised when the specified path is not a file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    if not os.path.isfile(path):
        raise ValueError(f"Not a file: {path}")

    file_size = os.path.getsize(path)

    content_type, _ = mimetypes.guess_type(path)

    return {
        "path": path,
        "filename": os.path.basename(path),
        "content_type": content_type,
        "bytes": file_size,
    }
