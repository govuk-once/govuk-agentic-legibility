"""
Task execution handlers for the generic BPMN workflow runner.

This module provides implementations for executing BPMN task types
encountered during workflow execution.

The BPMN definition controls workflow progression and determines
which task should execute next. These handlers provide the runtime
implementation for specific task types:

* User Tasks
    - Collect data from a user.
    - Validate and transform inputs.
    - Store results in workflow data.

* Service Tasks
    - Invoke external HTTP services.
    - Build request payloads from workflow data.
    - Persist service responses back into workflow state.
"""

import json
import logging
import os
from typing import Any

import requests

from bpmn.helper import (
    get_metadata,
    interpolate_object,
    interpolate_string,
    process_file_field,
)

logger = logging.getLogger(__name__)


def execute_user_task(
    task: Any,
) -> None:
    """
    Execute a BPMN User Task.

    The task definition is expected to contain metadata describing
    the form fields that should be presented to the user.

    User input is collected, optionally transformed, and stored
    within task data before the task is completed.

    Supported field types include:

    * text
    * number
    * boolean
    * file

    Args:
        task:
            User task being executed.

    Raises:
        Exception:
            Any unexpected errors encountered while collecting
            or processing user input.
    """
    try:
        metadata = get_metadata(task)

        logger.info(
            "Executing user task: %s",
            task.task_spec.name,
        )

        form = metadata.get("form", {})
        fields = form.get("fields", [])

        values: dict[str, Any] = {}

        if not fields:
            input("Press Enter to complete task...")

            task.complete()

            logger.info(
                "Completed user task: %s",
                task.task_spec.name,
            )

            return

        for field in fields:
            field_id = field.get("id")

            label = field.get(
                "label",
                field_id,
            )

            required = field.get(
                "required",
                False,
            )

            while True:
                value = input(f"{label}: ").strip()

                if field.get("type") == "file":
                    try:
                        value = process_file_field(value)
                        break

                    except Exception:
                        logger.exception(
                            "Failed to process file field '%s'",
                            field_id,
                        )
                        continue

                if value or not required:
                    break

                logger.warning(
                    "Field '%s' is required",
                    field_id,
                )

            values[field_id] = value

        if values:
            task.set_data(**values)

            logger.debug(
                "Stored user task data: %s",
                values,
            )

        task.complete()

        logger.info(
            "Completed user task: %s",
            task.task_spec.name,
        )

    except Exception:
        logger.exception(
            "Failed to execute user task: %s",
            task.task_spec.name,
        )
        raise


def execute_service_task(
    task: Any,
) -> None:
    """
    Execute a BPMN Service Task.

    Service task configuration is loaded from task metadata and
    used to construct an HTTP request.

    Request payloads may contain workflow variables which are
    dynamically interpolated before the request is sent.

    Supported HTTP methods:

    * GET
    * POST

    The response is optionally stored in workflow data using
    the configured result variable.

    Args:
        task:
            Service task being executed.

    Raises:
        RuntimeError:
            Raised when:

            * No endpoint is configured.
            * An unsupported HTTP method is specified.
            * The request fails.
            * A non-success response is returned.
    """
    try:
        metadata = get_metadata(task)

        logger.info(
            "Executing service task: %s",
            task.task_spec.name,
        )

        service = metadata.get(
            "service",
            {},
        )

        method = service.get(
            "method",
            "GET",
        )

        endpoint = service.get("endpoint")

        if endpoint:
            endpoint = interpolate_string(
                endpoint,
                task.data,
            )

        result_variable = service.get("result_variable")

        base_url = os.environ.get(
            "API_BASE_URL",
            "http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com",
        )

        if not endpoint:
            raise RuntimeError(
                f"Service task {task.task_spec.name} does not define an endpoint"
            )

        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        logger.info(
            "HTTP %s %s",
            method,
            url,
        )

        payload: dict[str, Any] = {}

        try:
            payload = task.data

        except Exception:
            logger.exception("Failed to retrieve workflow data")

        request_body = service.get("request_body")

        if request_body:
            payload = interpolate_object(
                request_body,
                task.data,
            )

        try:
            logger.debug(
                "Request payload:\n%s",
                json.dumps(
                    payload,
                    indent=2,
                    default=str,
                ),
            )
        except Exception:
            logger.debug(
                "Request payload: %s",
                payload,
            )

        try:
            if method.upper() == "GET":
                response = requests.get(
                    url,
                    params=payload,
                    timeout=30,
                )

            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    json=payload,
                    timeout=30,
                )

            else:
                raise RuntimeError(f"Unsupported method: {method}")

        except requests.RequestException as ex:
            logger.exception("HTTP request failed")

            raise RuntimeError(f"HTTP request failed: {ex}") from ex

        logger.info(
            "Response: %s %s",
            response.status_code,
            response.reason,
        )

        logger.debug(
            "Raw response:\n%s",
            response.text,
        )

        if not response.ok:
            raise RuntimeError(
                f"""
                Service task failed

                Task:
                {task.task_spec.name}

                Status:
                {response.status_code}

                Request Payload:
                {json.dumps(payload, indent=2, default=str)}

                Response:
                {response.text}
                """
            )

        try:
            result = response.json()

        except Exception:
            result = response.text

        try:
            logger.debug(
                "Parsed response:\n%s",
                json.dumps(
                    result,
                    indent=2,
                    default=str,
                ),
            )

        except Exception:
            logger.debug(
                "Parsed response: %s",
                result,
            )

        if result_variable:
            logger.info(
                "Updating workflow variable '%s'",
                result_variable,
            )

            task.set_data(**{result_variable: result})

        try:
            logger.debug(
                "Task data after update:\n%s",
                json.dumps(
                    task.data,
                    indent=2,
                    default=str,
                ),
            )

        except Exception:
            logger.debug(
                "Task data after update: %s",
                task.data,
            )

        task.complete()

        logger.info(
            "Completed service task: %s",
            task.task_spec.name,
        )

    except Exception:
        logger.exception(
            "Failed to execute service task: %s",
            task.task_spec.name,
        )
        raise


def execute_task(
    task: Any,
) -> None:
    """
    Execute a workflow task.

    This dispatcher determines the task type and routes execution
    to the appropriate handler implementation.

    Currently supported task types are:

    * UserTask
    * ServiceTask

    Any other task types are delegated back to the workflow engine
    via the task's native run() implementation.

    Args:
        task:
            Task selected for execution.

    Raises:
        Exception:
            Any exception raised by the underlying handler is
            propagated to the caller.
    """
    try:
        spec_name = task.task_spec.__class__.__name__

        logger.info(
            "Executing task '%s' (%s)",
            task.task_spec.name,
            spec_name,
        )

        if "UserTask" in spec_name:
            execute_user_task(
                task,
            )

            return

        if "ServiceTask" in spec_name:
            execute_service_task(
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
