"""
Activities bridging the BPMN interpreter
to external services.
"""

import asyncio
import logging
import os
from typing import Any

import httpx
from temporalio import activity

from bpmn.temporal_engine.bpmn_model import (
    HttpRequest,
)

from bpmn.temporal_engine.paths import (
    resolve_path,
    set_path,
)

logger = logging.getLogger(__name__)


#
# Maps BPMN service identifiers
# to environment variables.
#
API_BASE_URLS = {
    "dvla": "DVLA_BASE",
    "postoffice": "POSTOFFICE_BASE",
    "hmrc": "HMRC_BASE",
    "dwp": "DWP_BASE",
}


def _resolve_literal(
    expression: str,
) -> Any:
    """
    Support simple BPMN literal mappings.

    Examples:

        true
        false
        123
        hello
    """

    value = expression.strip()

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    return None


@activity.defn(name="http_call")
async def http_call(
    request: HttpRequest,
) -> dict[str, Any]:
    """
    Execute HTTP request using BPMN metadata.

    Returns mapped workflow variables.

    Example:

        {
            "photo_id": "img_123",
            "icao_compliant": True,
        }
    """

    logger.info(
        "HTTP activity "
        f"service={request.service} "
        f"method={request.method} "
        f"endpoint={request.endpoint}"
    )

    env_var = API_BASE_URLS.get(
        request.service.lower(),
    )

    if env_var is None:
        raise ValueError(
            f"Unknown service '{request.service}'"
        )

    base_url = os.environ.get(
        env_var,
        "http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com",
    )

    if not base_url:
        raise ValueError(
            f"Environment variable '{env_var}' is not configured"
        )

    full_url = f"{base_url}{request.endpoint}"

    #
    # Timeout
    #

    timeout_seconds = 30

    if request.timeout is not None:
        try:
            timeout_seconds = int(
                request.timeout.duration
                .replace("PT", "")
                .replace("S", "")
            )
        except Exception:
            logger.warning(
                "Invalid timeout duration '%s'",
                request.timeout.duration,
            )

    #
    # Retry
    #

    attempts = 1
    backoff_seconds = 0

    if request.retry is not None:
        attempts = request.retry.attempts
        backoff_seconds = request.retry.backoffSeconds

    last_exception = None

    for attempt in range(
        1,
        attempts + 1,
    ):
        try:
            logger.info(
                "HTTP attempt %s/%s",
                attempt,
                attempts,
            )

            async with httpx.AsyncClient(
                timeout=timeout_seconds,
            ) as client:

                response = await client.request(
                    method=request.method,
                    url=full_url,
                    json=request.body,
                )

            logger.info(
                "%s %s -> %s",
                request.method,
                full_url,
                response.status_code,
            )

            #
            # Retryable responses
            #

            if (
                response.status_code >= 500
                or response.status_code == 429
            ):
                raise RuntimeError(
                    f"HTTP {response.status_code}"
                )

            #
            # Business / client failures
            #

            if response.status_code >= 400:
                raise ValueError(
                    f"HTTP {response.status_code}"
                )

            break

        except Exception as exc:
            last_exception = exc

            if attempt >= attempts:
                raise

            logger.warning(
                "Retrying after error: %s",
                exc,
            )

            if backoff_seconds > 0:
                await asyncio.sleep(
                    backoff_seconds,
                )

    if last_exception and response is None:
        raise last_exception

    #
    # Parse body
    #

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if content_type.startswith(
        "application/json"
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

    #
    # Apply BPMN output mappings
    #

    mapped_variables: dict[str, Any] = {}

    for mapping in request.output_mappings:

        value = resolve_path(
            context,
            mapping.source,
        )

        #
        # Handle literal expressions.
        #
        # Example:
        #
        # source="true"
        #

        if value is None:
            value = _resolve_literal(
                mapping.source,
            )

        set_path(
            mapped_variables,
            mapping.target,
            value,
        )

        logger.info(
            "Mapped %s -> %s",
            mapping.source,
            mapping.target,
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

    Future implementations may route
    to email, SMS or GOV.UK Notify.
    """

    logger.info(
        "Notification sent: %s",
        params,
    )

    return {
        "sent": True,
    }