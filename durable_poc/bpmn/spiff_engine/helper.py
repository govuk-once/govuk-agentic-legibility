"""
Helper functions for BPMN workflow execution.
"""

from __future__ import annotations

import mimetypes
import re
import base64
from pathlib import Path
from typing import Any

WORKFLOW_METADATA: dict[str, dict[str, Any]] = {}

def register_workflow_metadata(
    metadata: dict[str, dict[str, Any]],
) -> None:
    """
    Register BPMN metadata loaded from the BPMN file.
    """

    WORKFLOW_METADATA.clear()

    WORKFLOW_METADATA.update(
        metadata,
    )


def get_metadata(
    task: Any,
) -> dict[str, Any]:
    """
    Return BPMN metadata for a task.
    """

    task_id = getattr(
        task.task_spec,
        "bpmn_id",
        None,
    )

    if task_id is None:
        return {}

    return WORKFLOW_METADATA.get(
        task_id,
        {},
    )


def apply_mappings(
    workflow_data: dict[str, Any],
    mappings: list[dict[str, str]],
) -> None:
    """
    Apply BPMN mapping definitions.
    """

    for mapping in mappings:

        source = mapping["source"]
        target = mapping["target"]

        value = get_nested_value(
            workflow_data,
            source,
        )

        set_nested_value(
            workflow_data,
            target,
            value,
        )

def interpolate_string(
    text: str,
    workflow_data: dict[str, Any],
) -> str:
    """
    Replace BPMN variable references.

    Example:

        ${applicant.first_name}
    """

    def replace(
        match: re.Match[str],
    ) -> str:

        path = match.group(1)

        value = get_nested_value(
            workflow_data,
            path,
            "",
        )

        return str(value)

    return re.sub(
        r"\$\{([^}]+)\}",
        replace,
        text,
    )


def get_nested_value(
    data: dict[str, Any],
    path: str,
    default: Any = None,
) -> Any:
    """
    Resolve a dotted path from a dictionary.

    Example:

        applicant.first_name
    """
    if not path:
        return data

    current = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return default

        current = current.get(part)

        if current is None:
            return default

    return current


def set_nested_value(
    data: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    """
    Set a dotted property path.

    Example:

        applicant.first_name
    """
    if not path:
        return

    current = data

    parts = path.split(".")

    for part in parts[:-1]:

        existing = current.get(part)

        if not isinstance(
            existing,
            dict,
        ):
            existing = {}
            current[part] = existing

        current = existing

    current[parts[-1]] = value


def process_file_field(
    path: str,
) -> dict[str, Any]:
    """
    Convert uploaded file into metadata object.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(path)

    mime_type = mimetypes.guess_type(path)[0]

    with open(file_path, "rb") as fp:
        content = fp.read()

    content_base64 = (base64.b64encode(content).decode("ascii"))

    return {
        "filename": file_path.name,
        "content_type": mime_type,
        "size": len(content),
        "content": content_base64,
    }


def build_request_payload(
    mappings: list[dict[str, str]],
    workflow_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build request payload from BPMN mappings.
    """

    payload: dict[str, Any] = {}

    for mapping in mappings:

        source = mapping["source"]
        target = mapping["target"]

        value = get_nested_value(
            workflow_data,
            source,
        )

        set_nested_value(
            payload,
            target,
            value,
        )

    return payload


def apply_output_mappings(
    workflow_data: dict[str, Any],
    response_data: dict[str, Any],
    mappings: list[dict[str, str]],
) -> None:
    """
    Apply BPMN output mappings.
    """

    response_context = {
        "response": response_data,
    }

    for mapping in mappings:

        source = mapping["source"]
        target = mapping["target"]

        value = get_nested_value(
            response_context,
            source,
        )

        set_nested_value(
            workflow_data,
            target,
            value,
        )