"""
Task execution handlers for the generic BPMN workflow runner.

The BPMN definition controls workflow progression while these
handlers provide runtime implementations for executable tasks.
"""

from __future__ import annotations

from SpiffWorkflow.task import TaskState

import json
import logging
import os
import time
from copy import deepcopy
from typing import Any

import requests

from bpmn.helper import (
    apply_mappings,
    apply_output_mappings,
    build_request_payload,
    get_metadata,
    interpolate_string,
    process_file_field,
    set_nested_value,
)

logger = logging.getLogger(__name__)


def get_executable_tasks(
    workflow: Any,
) -> list[Any]:
    """
    Return BPMN tasks ready for execution.

    Internal Spiff-generated tasks are excluded.
    """

    executable: list[Any] = []

    for task in workflow.get_tasks():

        if task.task_spec.bpmn_id is None:
            continue

        if task.has_state(TaskState.READY) or task.has_state(TaskState.STARTED):
            executable.append(task)

    return executable


def execute_mapping_task(
    task: Any,
) -> None:
    """
    Execute a BPMN mapping task.
    """

    metadata = get_metadata(task)

    mapping = metadata.get(
        "mapping",
        {},
    )

    outputs = mapping.get(
        "outputs",
        [],
    )

    workflow_updates = deepcopy(
        task.data,
    )

    apply_mappings(
        workflow_updates,
        outputs,
    )

    task.set_data(
        **workflow_updates,
    )

    task.complete()

    logger.info(
        "Completed mapping task: %s",
        task.task_spec.name,
    )


def execute_manual_task(
    task: Any,
) -> None:
    """
    Execute a BPMN Manual Task.
    """

    logger.warning(
        "Manual processing required: %s",
        task.task_spec.name,
    )

    input(
        "\nManual processing required."
        "\nPress Enter when complete..."
    )

    task.complete()

    logger.info(
        "Manual task completed: %s",
        task.task_spec.name,
    )


def execute_user_task(
    task: Any,
) -> None:
    """
    Execute a BPMN User Task.
    """

    try:

        metadata = get_metadata(task)

        form = metadata.get(
            "form",
            {},
        )

        fields = form.get(
            "fields",
            [],
        )

        logger.info(
            "Executing user task: %s",
            task.task_spec.name,
        )

        if not fields:

            input(
                "Press Enter to complete task..."
            )

            task.complete()

            return

        workflow_updates: dict[str, Any] = {}

        for field in fields:

            field_id = field.get(
                "id",
            )

            variable = field.get(
                "variable",
                field_id,
            )

            label = field.get(
                "label",
                field_id,
            )

            required = (
                str(
                    field.get(
                        "required",
                        False,
                    )
                ).lower()
                == "true"
            )

            field_type = field.get(
                "type",
                "string",
            )

            while True:

                value = input(
                    f"{label}: "
                ).strip()

                if field_type == "file":

                    try:

                        value = process_file_field(
                            value,
                        )

                        break

                    except Exception:

                        logger.exception(
                            "Failed processing file '%s'",
                            field_id,
                        )

                        continue

                if value or not required:
                    break

                logger.warning(
                    "Field '%s' is required",
                    field_id,
                )

            set_nested_value(
                workflow_updates,
                variable,
                value,
            )

        if workflow_updates:

            logger.debug(
                "Workflow updates: %s",
                workflow_updates,
            )

            task.set_data(
                **workflow_updates,
            )

        task.complete()

        logger.info(
            "Completed user task: %s",
            task.task_spec.name,
        )

    except Exception:

        logger.exception(
            "Failed user task: %s",
            task.task_spec.name,
        )

        raise


def execute_service_task(
    task: Any,
) -> None:
    """
    Execute a BPMN HTTP service task.
    """

    try:

        metadata = get_metadata(task)

        service = metadata.get(
            "httpService",
            {},
        )

        logger.info(
            "Executing service task: %s",
            task.task_spec.name,
        )

        endpoint = service.get(
            "endpoint",
        )

        if not endpoint:

            raise RuntimeError(
                f"No endpoint configured for "
                f"{task.task_spec.name}"
            )

        endpoint = interpolate_string(
            endpoint,
            task.data,
        )

        base_url = os.environ.get(
            "API_BASE_URL",
            "http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com",
        )

        url = (
            f"{base_url.rstrip('/')}"
            f"/{endpoint.lstrip('/')}"
        )

        method = service.get(
            "method",
            "GET",
        ).upper()

        timeout_cfg = service.get(
            "timeout",
            {},
        )

        timeout = 30

        duration = timeout_cfg.get(
            "duration",
        )

        if (
            isinstance(duration, str)
            and duration.startswith("PT")
            and duration.endswith("S")
        ):
            timeout = int(
                duration[2:-1]
            )

        retry = service.get(
            "retry",
            {},
        )

        attempts = int(
            retry.get(
                "attempts",
                1,
            )
        )

        backoff = int(
            retry.get(
                "backoffSeconds",
                0,
            )
        )

        payload = build_request_payload(
            service.get(
                "inputs",
                [],
            ),
            task.data,
        )

        try:

            logger.debug(
                "Payload:\n%s",
                json.dumps(
                    payload,
                    indent=2,
                    default=str,
                ),
            )

        except Exception:

            logger.debug(
                "Payload: %s",
                payload,
            )

        response = None

        for attempt in range(
            attempts,
        ):

            try:

                logger.info(
                    "HTTP %s %s "
                    "(attempt %s/%s)",
                    method,
                    url,
                    attempt + 1,
                    attempts,
                )

                if method == "GET":

                    response = requests.get(
                        url,
                        params=payload,
                        timeout=timeout,
                    )

                elif method == "POST":

                    response = requests.post(
                        url,
                        json=payload,
                        timeout=timeout,
                    )

                else:

                    raise RuntimeError(
                        f"Unsupported method: "
                        f"{method}"
                    )

                break

            except requests.RequestException:

                logger.exception(
                    "HTTP request failed"
                )

                if attempt >= attempts - 1:
                    raise

                time.sleep(
                    backoff,
                )

        if response is None:

            raise RuntimeError(
                "No response received"
            )

        logger.info(
            "Response: %s %s",
            response.status_code,
            response.reason,
        )

        if not response.ok:

            raise RuntimeError(
                f"Service task failed "
                f"({response.status_code})"
            )

        try:

            result = response.json()

        except Exception:

            result = {
                "value": response.text,
            }

        try:

            logger.debug(
                "Response payload:\n%s",
                json.dumps(
                    result,
                    indent=2,
                    default=str,
                ),
            )

        except Exception:

            logger.debug(
                "Response payload: %s",
                result,
            )

        workflow_updates = deepcopy(
            task.data,
        )

        apply_output_mappings(
            workflow_updates,
            result,
            service.get(
                "outputs",
                [],
            ),
        )

        task.set_data(
            **workflow_updates,
        )

        task.complete()

        logger.info(
            "Completed service task: %s",
            task.task_spec.name,
        )

    except Exception:

        logger.exception(
            "Failed service task: %s",
            task.task_spec.name,
        )

        raise


def execute_task(
    task: Any,
) -> None:
    """
    Execute a workflow task.
    """

    try:

        metadata = get_metadata(
            task,
        )

        handler_type = (
            metadata.get(
                "taskHandler",
                {},
            )
            .get("type")
        )

        logger.info(
            "Executing task '%s' "
            "(handler=%s)",
            task.task_spec.name,
            handler_type,
        )

        if handler_type == "manual":

            execute_manual_task(
                task,
            )

            return

        if handler_type == "form":

            execute_user_task(
                task,
            )

            return

        if handler_type == "http":

            execute_service_task(
                task,
            )

            return

        if handler_type == "mapping":

            execute_mapping_task(
                task,
            )

            return

        logger.debug(
            "Executing engine-managed task: %s",
            task.task_spec.name,
        )

        task.run()

    except Exception:

        logger.exception(
            "Task execution failed: %s",
            task.task_spec.name,
        )

        raise