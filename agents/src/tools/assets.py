import logging
import sys
import boto3
from mypy_boto3_secretsmanager import SecretsManagerClient
from botocore.exceptions import ClientError
from dataclasses import dataclass
import jwt
import time
from enum import Enum

REDIRECT_URI = "govuk://govuk/login-auth-callback"


# Helpers
def get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_secrets_client(region="eu-west-2"):
    return boto3.client(service_name="secretsmanager", region_name=region)


def get_secret(
    client: SecretsManagerClient, logger: logging.Logger, secret_id: str
) -> str | None:
    try:
        return client.get_secret_value(
            SecretId=secret_id,
        ).get("SecretString")
    except ClientError as c:
        logger.error(f"Error while retrieving secret {secret_id}: {str(c)}")
        raise


def write_secret(
    client: SecretsManagerClient,
    logger: logging.Logger,
    secret_id: str,
    secret_value: str,
) -> str | None:
    try:
        return client.put_secret_value(
            SecretId=secret_id, SecretString=secret_value
        ).get("ARN")
    except ClientError as c:
        logger.error(f"Error while writing secret {secret_id}: {str(c)}")
        raise


class TokenGenerator:
    def generate_new_token(self):
        pass


class TokenWrangler:
    def __init__(
        self, generator: TokenGenerator, logger: logging.Logger, token_type: TokenType
    ) -> None:
        self.generator = generator
        self.logger = logger
        self.token_type = token_type

    def get_or_create_token(self, secret_id: str) -> TokenResult:
        """Gets token if stored in Secrets Manager or generates one.
        
        The token specified at the given secret_id is retrieved. For a DVLA token, it is automatically 
        regenerated as it is dependent on the customer id which can change. For a Flex token, we check the TTL
        and if it less than 60 seconds, we generate a new one and store it before returning it.

        Args:
            secret_id (str): the id of the token stored in Secrets Manager

        Returns:
            TokenResult

        """
        ttl = None
        current_token = self.get_token_from_secrets(secret_id)

        if self.token_type == TokenType.FLEX:
            if current_token and (ttl:=self.check_jwt_validity(current_token)) > 60:
                return TokenResult(stored=True, ttl=ttl, token=current_token, token_type=self.token_type.value)
            
        if current_token:
            new_token = self.generator.generate_new_token()
            if new_token:
                return self.write_token_to_secrets(new_token, secret_id)
           
        return TokenResult(stored=False, token_type=self.token_type.value)

    def get_token_from_secrets(self, secret_id: str) -> str | None:
        try:
            secretsm = get_secrets_client()
            return get_secret(secretsm, self.logger, secret_id)
        except ClientError as c:
            self.logger.error(f"Error while retrieving token from Secrets: {str(c)}")
            sys.exit(1)

    def write_token_to_secrets(self, token: str, secret_id: str) -> TokenResult:
        ttl = 0
        if self.token_type == TokenType.FLEX:
            ttl = self.check_jwt_validity(token)
        try:
            secretsm = get_secrets_client()
            result = write_secret(secretsm, self.logger, secret_id, token)
            if result:
                return TokenResult(
                    stored=True, token_type=self.token_type.value, ttl=ttl, token=token
                )
            else:
                return TokenResult(
                    stored=False, token_type=self.token_type.value, ttl=ttl, token=token
                )
        except ClientError as c:
            self.logger.error(f"Problem writing token to secrets: {str(c)}")
            return TokenResult(
                stored=False, token_type=self.token_type.value, ttl=ttl, token=token
            )

    def check_jwt_validity(self, token: str) -> int:
        """Checks JWT valid and checks time to expiry in seconds."""
        try:
            if self.token_type == TokenType.FLEX:
                return 0
            claims = jwt.decode(token, options={"verify_signature": False})
            if "exp" not in claims:
                return 0
            time_remaining = int(claims["exp"]) - int(time.time())
            return max(0, time_remaining)
        except jwt.InvalidTokenError:
            self.logger.warning("Flex token is not valid")
            return 0


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


class TokenType(Enum):
    FLEX = "flex"
    DVLA = "dvla"


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
    token_type: str
    ttl: int | None = 0
    token: str | None = None
