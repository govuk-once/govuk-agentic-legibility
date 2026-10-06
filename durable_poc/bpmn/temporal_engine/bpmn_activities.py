"""
Activities bridging the BPMN interpreter to external services.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from temporalio import activity

from bpmn.temporal_engine.bpmn_parser import (
    parse_bpmn_file,
    parse_process_file,
)
from bpmn.temporal_engine.process_registry import (
    PROCESS_REGISTRY,
)

from src.paths import (
    resolve_literal,
    resolve_path,
    set_path,
)

logger = logging.getLogger(__name__)

_PROCESS_CACHE: dict[str, dict[str, Any]] = {}

API_BASE_URLS = {
    "dvla": "DVLA_BASE",
    "postoffice": "POSTOFFICE_BASE",
    "hmrc": "HMRC_BASE",
    "dwp": "DWP_BASE",
}


@activity.defn(name="http_call")
async def http_call(
    request: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute an HTTP request defined in BPMN metadata.
    """

    logger.info(
        "HTTP activity service=%s method=%s endpoint=%s",
        request["service"],
        request["method"],
        request["endpoint"],
    )

    env_var = API_BASE_URLS.get(
        request["service"].lower(),
    )

    if env_var is None:
        raise ValueError(
            f"Unknown service '{request['service']}'"
        )

    base_url = os.environ.get(
        env_var,
        "http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com",
    )

    if not base_url:
        raise ValueError(
            f"Environment variable '{env_var}' is not configured"
        )

    full_url = f"{base_url}{request['endpoint']}"

    timeout_seconds = 30

    if request.get("timeout"):
        try:
            timeout_seconds = int(
                request["timeout"]["duration"]
                .replace("PT", "")
                .replace("S", "")
            )
        except Exception:
            logger.warning(
                "Invalid timeout duration %s",
                request["timeout"]["duration"],
            )

    async with httpx.AsyncClient(
        timeout=timeout_seconds,
    ) as client:

        logger.info(
            "%s %s",
            request["method"],
            full_url,
        )

        response = await client.request(
            method=request["method"],
            url=full_url,
            json=request.get("body") or None,
        )

        logger.info(
            "%s -> %s",
            full_url,
            response.status_code,
        )

        response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if content_type.startswith(
        "application/json",
    ):
        body = response.json()
    else:
        body = response.text

    context = {
        "response": {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        }
    }

    mapped_variables: dict[str, Any] = {}

    for mapping in request["output_mappings"]:

        source = mapping["source"]
        target = mapping["target"]

        value = resolve_path(
            context,
            source,
        )

        if value is None:
            value = resolve_literal(
                source,
            )

        set_path(
            mapped_variables,
            target,
            value,
        )

        logger.info(
            "Mapped %s -> %s",
            source,
            target,
        )

    logger.info(
        "HTTP activity completed successfully"
    )

    return mapped_variables


@activity.defn(name="send_notification")
async def send_notification(
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Placeholder notification activity.
    """

    logger.info(
        "Notification sent: %s",
        params,
    )

    return {
        "sent": True,
    }


@activity.defn(name="load_definition")
async def load_definition(
    process_id: str,
) -> dict[str, Any]:
    """
    Load a root BPMN definition using the process registry.
    """

    logger.info(
        "Loading BPMN definition process_id=%s",
        process_id,
    )

    process_path = PROCESS_REGISTRY.get(
        process_id,
    )

    if process_path is None:
        raise ValueError(
            f"Unknown BPMN process '{process_id}'"
        )

    definition = parse_bpmn_file(
        process_path,
    )

    result = definition.model_dump(
        mode="json",
    )

    logger.info(
        "Loaded BPMN definition id=%s version=%s",
        result.get("id"),
        result.get("version"),
    )

    return result


@activity.defn(name="load_process")
async def load_process(
    process_path: str,
) -> dict[str, Any]:
    """
    Lazily load a BPMN subprocess.
    """

    logger.info(
        "Loading BPMN subprocess %s",
        process_path,
    )

    if process_path in _PROCESS_CACHE:

        logger.info(
            "Using cached subprocess %s",
            process_path,
        )

        return _PROCESS_CACHE[
            process_path
        ]

    process = parse_process_file(
        process_path,
    )

    result = process.model_dump(
        mode="json",
    )

    _PROCESS_CACHE[
        process_path
    ] = result

    logger.info(
        "Loaded subprocess id=%s",
        result.get("id"),
    )

    return result