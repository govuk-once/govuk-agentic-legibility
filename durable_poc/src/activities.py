"""Activities bridging the workflow to external services."""

import logging
from typing import Any
from dataclasses import dataclass
import os
from json import JSONDecodeError

import httpx
from temporalio import activity
from opentelemetry import trace

from src.errors import RetryableHttpError, ValidationError
from src.model import CaptureSpec
from src.paths import resolve_path

logger = logging.getLogger(__name__)


def _workflow_id_from_activity() -> str | None:
    """Return the workflow ID if running inside a Temporal activity, else None."""
    if not activity.in_activity():
        return None
    return activity.info().workflow_id

# Config-driven service routing table (Maps workflow definition 'service' keys to ENV variables)
SERVICE_ENV_MAP = {
    "dvla": "DVLA_BASE",
    "postoffice": "POSTOFFICE_BASE",
    "hmrc": "HMRC_BASE",
    "dwp": "DWP_BASE",
}


@dataclass
class CallParams:
    """Parameters required by the http_call activity."""
    method: str
    url: str
    service: str
    headers: dict[str, str] | None = None
    body: dict[str, Any] | None = None
    capture: dict[str, str | CaptureSpec] | None = None
    idempotency_key: str | None = None
    timeout_seconds: float = 15.0


@activity.defn
async def http_call(params: CallParams) -> dict[str, Any]:
    """Execute an HTTP call with idempotency headers and projected captures."""
    span = trace.get_current_span()
    wf_id = _workflow_id_from_activity()
    if wf_id:
        span.set_attribute("workflow_id", wf_id)
    span.set_attribute("service", params.service)
    span.set_attribute("http.method", params.method)
    span.set_attribute("http.url", params.url)
    if params.idempotency_key:
        span.set_attribute("idempotency_key", params.idempotency_key)

    if params.service in SERVICE_ENV_MAP:
        env_var = SERVICE_ENV_MAP[params.service]
        base_url = os.environ.get(env_var)
        if not base_url:
            raise ValidationError(
                f"Required environment variable '{env_var}' is not configured"
            )
    elif params.service:
        base_url = os.environ.get(params.service.upper())
        if not base_url:
            raise ValidationError(
                f"Unrecognised or unconfigured HTTP service: '{params.service}'"
            )
    else:
        raise ValidationError(
            "HTTP call state missing required 'service' configuration"
        )

    full_url = f"{base_url}{params.url}"

    request_headers = {**(params.headers or {})}
    if params.idempotency_key:
        request_headers["Idempotency-Key"] = params.idempotency_key

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=params.method,
                url=full_url,
                headers=request_headers,
                json=params.body,
                timeout=params.timeout_seconds,
            )
        except httpx.RequestError as e:
            raise RetryableHttpError(f"HTTP request failed: {e}") from e

    span.set_attribute("http.status_code", response.status_code)

    if response.status_code >= 500 or response.status_code == 429:
        raise RetryableHttpError(f"HTTP {response.status_code}")

    body: dict[str, Any] = {}
    if response.headers.get("Content-Type", "").startswith("application/json"):
        try:
            body = response.json()
        except JSONDecodeError:
            body = {}

    full_context = {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }

    return _project_capture(full_context, params.capture)


def _project_capture(
    full_context: dict[str, Any],
    capture_spec: dict[str, str | CaptureSpec] | None,
) -> dict[str, Any]:
    """Apply the capture specification to the raw HTTP context."""
    if not capture_spec:
        return {}

    result: dict[str, Any] = {}
    for key, spec in capture_spec.items():
        if isinstance(spec, str):
            result[key] = resolve_path(full_context, spec)
            continue
        if isinstance(spec, CaptureSpec):
            source = resolve_path(full_context, spec.from_)

            if isinstance(source, list):
                projected = source
                if spec.pick:
                    projected = [
                        {field: item.get(field) for field in spec.pick}
                        if isinstance(item, dict)
                        else item
                        for item in projected
                    ]

                if spec.max_items:
                    projected = projected[: spec.max_items]

                result[key] = projected

            elif isinstance(source, str) and spec.max_length:
                result[key] = source[: spec.max_length]

            else:
                result[key] = source
            continue

        if isinstance(spec, dict):
            source = resolve_path(full_context, spec.get("from", ""))
            result[key] = source
    return result


@dataclass
class NotifyParams:
    """Parameters required by the notify activity."""
    channel: str
    template: str | None = None
    message: str | None = None
    params: dict[str, Any] | None = None


@activity.defn
async def notify(params: NotifyParams) -> None:
    """Mock notification activity."""
    span = trace.get_current_span()
    wf_id = _workflow_id_from_activity()
    if wf_id:
        span.set_attribute("workflow_id", wf_id)
    span.set_attribute("channel", params.channel)
    span.set_attribute("template", params.template)
    logger.info(
        "Notification sent channel=%s template=%s message=%s params=%s",
        params.channel,
        params.template,
        params.message,
        params.params,
    )


@activity.defn
async def load_workflow_definition(
    workflow_id: int,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Load and assemble a workflow definition from the Workflow Server.
    """
    span = trace.get_current_span()
    wf_id = _workflow_id_from_activity()
    if wf_id:
        span.set_attribute("workflow_id", wf_id)
    span.set_attribute("definition.workflow_id", workflow_id)
    workflow_server_url = (base_url or os.environ.get("WORKFLOW_SERVER_URL"))
    if not workflow_server_url:
        raise ValidationError(
            "WORKFLOW_SERVER_URL environment variable is not configured"
        )
    http_client = httpx.AsyncClient()
    close_client = True

    try:
        workflow_response = await http_client.get(
            f"{workflow_server_url}/api/v1/workflows/{workflow_id}",
            timeout=15.0,
        )

        if workflow_response.status_code == 404:
            raise ValidationError(
                f"Workflow {workflow_id} not found"
            )

        workflow_response.raise_for_status()
        definition = workflow_response.json()
        assembled_processes: dict[str, Any] = {}

        for process_ref in definition.get(
            "processes",
            [],
        ):
            process_id = process_ref.get("process_id")
            version = process_ref.get("version")

            if not process_id:
                raise ValidationError(
                    f"Process reference missing process_id: {process_ref}"
                )

            if not version:
                raise ValidationError(
                    f"Process reference missing version: {process_ref}"
                )

            process_response = await http_client.get(
                (
                    f"{workflow_server_url}"
                    f"/api/v1/processes/{process_id}/{version}"
                ),
                timeout=15.0,
            )

            if process_response.status_code == 404:
                raise ValidationError(
                    f"Process '{process_id}' version '{version}' not found"
                )

            process_response.raise_for_status()
            process_definition = process_response.json()
            actual_process_id = process_definition.get("process_id")

            if actual_process_id != process_id:
                raise ValidationError(
                    f"Expected process '{process_id}' "
                    f"but server returned '{actual_process_id}'"
                )

            assembled_processes[process_id] = process_definition
        entry_process = definition.get("entry")

        if entry_process not in assembled_processes:
            raise ValidationError(
                f"Entry process '{entry_process}' not found"
            )

        definition["processes"] = assembled_processes

        span.set_attribute("definition.process_count", len(assembled_processes))

        logger.info(
            "Loaded workflow '%s' (%s processes)",
            definition.get("id"),
            len(assembled_processes),
        )

        return definition

    finally:
        if close_client:
            await http_client.aclose()