"""Configuration helpers for locating the journey service."""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv
from botocore.exceptions import BotoCoreError, ClientError

from agents.src.workflow_executor.errors import JourneyConfigurationError

DEFAULT_AWS_REGION = "eu-west-2"
DEFAULT_STUB_SERVER_PARAMETER = "/flex-mock/server-url"
AGENTS_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_executor_environment() -> None:
    """Load configuration from ``agents/.env`` without overriding the process."""
    load_dotenv(dotenv_path=AGENTS_ENV_FILE, override=False)


def resolve_base_url(explicit_base_url: str | None = None) -> str:
    """Resolve the journey-service URL for local or deployed stub execution.

    Resolution order is:

    1. explicit function argument;
    2. `STUB_SERVER_URL` environment variable;
    3. `/flex-mock/server-url` in Parameter Store when `USE_STUB_SERVER=1`.

    Args:
        explicit_base_url: URL supplied directly by a caller or CLI option.

    Returns:
        Base URL of the configured journey service.

    Raises:
        JourneyConfigurationError: If no server is configured or Parameter Store cannot
            be queried.
    """
    if explicit_base_url:
        return explicit_base_url

    environment_url = os.environ.get("STUB_SERVER_URL")
    if environment_url:
        return environment_url

    if os.environ.get("USE_STUB_SERVER") == "1":
        region = os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)
        parameter_name = os.environ.get(
            "STUB_SERVER_PARAMETER",
            DEFAULT_STUB_SERVER_PARAMETER,
        )
        try:
            ssm = boto3.client("ssm", region_name=region)
            response = ssm.get_parameter(Name=parameter_name)
            parameter = response.get("Parameter", {})
            value = parameter.get("Value")
        except (BotoCoreError, ClientError) as exc:
            msg = f"Could not retrieve journey server URL from {parameter_name}"
            raise JourneyConfigurationError(msg) from exc

        if isinstance(value, str) and value:
            return value
        raise JourneyConfigurationError(
            f"Parameter Store value {parameter_name!r} is missing or empty"
        )

    raise JourneyConfigurationError(
        "Set --base-url, STUB_SERVER_URL, or USE_STUB_SERVER=1"
    )
