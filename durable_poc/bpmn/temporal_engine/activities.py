"""
Activities bridging the BPMN interpreter
to external services.
"""

import logging
import os
from typing import Any

import httpx
from temporalio import activity

from bpmn.temporal_engine.bpmn_model import (
    HttpRequest,
)

logger = logging.getLogger(__name__)


#
# Maps BPMN metadata service identifiers
# to environment variables.
#
API_BASE_URLS = {
    "dvla": "DVLA_BASE",
    "postoffice": "POSTOFFICE_BASE",
    "hmrc": "HMRC_BASE",
    "dwp": "DWP_BASE",
}


@activity.defn(name="http_call")
async def http_call(
    request: HttpRequest,
) -> dict[str, Any]:
    """
    Execute an HTTP request.

    Returns a response envelope that
    BPMN output mappings can consume.

    Example mappings:

        response.body.photo_id

        response.body.valid

        response.status
    """

    logger.info(
        "Executing HTTP activity "
        f"service={request.service} "
        f"method={request.method} "
        f"endpoint={request.endpoint}"
    )

    #
    # Resolve service base URL.
    #

    env_var = API_BASE_URLS.get(
        request.service.lower(),
    )

    if env_var is None:
        raise ValueError(f"Unknown service '{request.service}'")

    base_url = os.environ.get(
        env_var,
        "http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com",
    )

    if not base_url:
        raise ValueError(f"Environment variable '{env_var}' is not configured")

    full_url = f"{base_url}{request.endpoint}"

    logger.info(f"Resolved URL: {full_url}")

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request body: {request.body}")

            response = await client.request(
                method=request.method,
                url=full_url,
                json=request.body,
                timeout=15.0,
            )

    except httpx.RequestError as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc

    logger.info(f"HTTP {request.method} {full_url} -> {response.status_code}")

    #
    # Retryable server failures.
    #
    # Temporal retry policy will
    # automatically retry these.
    #

    if response.status_code >= 500 or response.status_code == 429:
        raise RuntimeError(f"HTTP {response.status_code}")

    #
    # Non-success responses.
    #
    # These can later be routed
    # through BPMN boundary events.
    #

    if response.status_code >= 400:
        logger.error(f"HTTP {response.status_code}: {response.text}")

        raise ValueError(f"HTTP {response.status_code}")

    body: Any = None

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if content_type.startswith("application/json"):
        try:
            body = response.json()

        except Exception:
            logger.warning("Unable to parse JSON response")

            body = None

    else:
        body = response.text

    result = {
        "status": response.status_code,
        "headers": dict(
            response.headers,
        ),
        "body": body,
    }

    logger.info("HTTP activity completed successfully")

    return result


@activity.defn
async def notify(
    params: dict[str, Any],
) -> None:
    """
    Mock outbound notification activity.
    """

    logger.info(f"Notify: {params}")
