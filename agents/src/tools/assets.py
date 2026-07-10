import logging
import sys
import boto3
from mypy_boto3_secretsmanager import SecretsManagerClient
from botocore.exceptions import ClientError
from dataclasses import dataclass

REDIRECT_URI = "govuk://govuk/login-auth-callback"


# Helpers
def get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_secrets_client(region="eu-west-2"):
    return boto3.client(service_name="secretsmanager", region_name=region)


def get_secret(client: SecretsManagerClient, logger: logging.Logger, secret_id: str) -> str | None:
    try:
        return client.get_secret_value(
            SecretId=secret_id,
        ).get("SecretString")
    except ClientError as c:
        logger.error(f"Error while retrieving secret {secret_id}: {str(c)}")
        return None


def write_secret(client: SecretsManagerClient, logger: logging.Logger, secret_id: str, secret_value: str) -> str | None:
    try:
        return client.put_secret_value(SecretId=secret_id, SecretString=secret_value).get("ARN")
    except ClientError as c:
        logger.error(f"Error while writing secret {secret_id}: {str(c)}")
        return None


# Errors
class NoCSRFException(Exception):
    pass


class NoRedirectURLException(Exception):
    pass


class NoCodeInURLException(Exception):
    pass


class TokenExchangeFailedException(Exception):
    pass


# Data Structures

@dataclass
class JwtAuthConfig:
    email: str
    password: str
    totp: str
    client_id: str
    auth_url: str
    token_url: str
    one_login_env: str
    redirect_uri: str = REDIRECT_URI
    attestation_token: str | None = None


@dataclass
class TokenResult:
    stored: bool
    ttl: int = 0
    token: str | None = None
