from agents.src.tools.authenticate_flex import FlexTokenGenerator
from agents.src.tools.authenticate_dvla import DVLATokenGenerator
from agents.src.tools.assets import TokenWrangler, TokenType, get_logger
from botocore.exceptions import ClientError, NoCredentialsError
from requests.exceptions import HTTPError
import boto3
import sys
from pathlib import Path
import requests
import json
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

USE_STUB_SERVER = os.environ.get("USE_STUB_SERVER", 1)
REQUEST_TIMEOUT_SECONDS = 30

logger = get_logger()


def get_stub_url():
    ssm = boto3.client("ssm", region_name="eu-west-2")

    parameter_name = "/flex-mock/server-url"

    try:
        response = ssm.get_parameter(Name=parameter_name)
        url = response["Parameter"].get("Value")
        return url

    except ClientError as e:
        logger.error(
            f"Failed to retrieve parameter: {e.response.get('Error', {}).get('Message')}"
        )
        return None


FLEX_BASE_URL = (
    "https://staging.bl.once.service.gov.uk/app"
    if USE_STUB_SERVER == "0"
    else get_stub_url()
)


def authenticate_and_match(user: str) -> str | None:
    logger.info("getting Flex token")
    env_path = (
        Path(__file__).resolve().parent.parent.parent / ".env"
    )  # perhaps hold these values in Parameter Store or Secrets Manager
    flex_gen = FlexTokenGenerator(env_path=env_path, logger=logger)
    flex_wrangler = TokenWrangler(
        generator=flex_gen, logger=logger, token_type=TokenType.FLEX
    )
    flex_token = flex_wrangler.get_or_create_token("flex-access-token").token

    logger.info("getting link token for user")
    dvla_gen = DVLATokenGenerator(user, logger=logger)
    dvla_wrangler = TokenWrangler(
        generator=dvla_gen, logger=logger, token_type=TokenType.DVLA
    )
    if USE_STUB_SERVER:
        dvla_token = str(uuid.uuid4())
    else:
        dvla_token = dvla_wrangler.get_or_create_token("dvla-linking-token").token # type: ignore[assignment]

    match_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {flex_token}",
        "x-linking-token": dvla_token,
    }
    match_url = f"{FLEX_BASE_URL}/app/udp/v1/identity/dvla"

    logger.info("Matching tokens")
    match_response = requests.post(
        match_url,
        headers=match_headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    logger.info(f"Match result = {match_response.status_code}")

    return flex_token


def get_user_data(user: str, override_token: str | None = None, retry: int = 1) -> dict:
    max_retries = 3
    try:
        if not override_token:
            secretsm = boto3.client("secretsmanager")
            flex_token = secretsm.get_secret_value(SecretId="flex-access-token")
        else:
            flex_token = override_token # type: ignore[assignment]
        logger.info("Getting user data")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {flex_token}",
        }
        url = f"{FLEX_BASE_URL}/app/dvla/v1/customer-summary"
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except secretsm.exceptions.ResourceNotFoundException:
        logger.error("The secret flex-access-token was not found")
        sys.exit(1)
    except ClientError as e:
        logger.error(f"There was an error retrieving the Flex token: {e}")
        sys.exit(1)
    except HTTPError as e:
        logger.info(f"HTTPError: {e}")
        # if 401 or 403 reauthenticate and retry
        if response.status_code in (401, 403) and retry < max_retries:
            logger.info("Retrying authentication...")
            token = authenticate_and_match(user)
            return get_user_data(user, override_token=token, retry=retry + 1)
        elif response.status_code in (401, 403):
            logger.info("Max retries exceeded, halting")
            sys.exit(1)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error {e}")
        raise e


if __name__ == "__main__":
    users = {
        "bill": "8bc39b9f-9cdc-4dc6-8364-632d1f7b5916",  # has no vehicles
        "belinda": "b32e769a-dd78-48b9-bde4-3b229b9b6c8e",  # Has vehicle, untaxed
        "bob": "c3375b6d-e3b8-46c9-895e-e257440b36bc",  # Has taxed vehicle
        "bertha": "49fec1c5-0712-4a2d-9116-406eb147ff7a",  # Has few vehicles
    }

    try:
        sts = boto3.client("sts")
        sts.get_caller_identity()
    except (ClientError, NoCredentialsError) as c:
        logger.error(f"Error connecting to AWS account: {str(c)}")
        sys.exit()

    user = users["bob"]
    flex_token = authenticate_and_match(user)
    print(flex_token)
    data = get_user_data(user)
    print(json.dumps(data, indent=2))
