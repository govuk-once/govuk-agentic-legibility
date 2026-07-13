from agents.src.tools.authenticate_flex import FlexTokenGenerator
from agents.src.tools.authenticate_dvla import DVLATokenGenerator
from agents.src.tools.assets import TokenWrangler, TokenType, get_logger
from botocore.exceptions import ClientError
from requests.exceptions import HTTPError
import boto3
import sys
import json
from pathlib import Path
import requests


logger = get_logger()

FLEX_BASE_URL = "https://staging.bl.once.service.gov.uk/app"

def authenticate_and_match(user: str) -> str | None:
    logger.info("getting Flex token")
    env_path = Path(__file__).resolve().parent.parent.parent / ".env" # perhaps hold these values in Parameter Store or Secrets Manager
    flex_gen = FlexTokenGenerator(env_path=env_path, logger=logger)
    flex_wrangler = TokenWrangler(generator=flex_gen, logger=logger, token_type=TokenType.FLEX)
    flex_token = flex_wrangler.get_or_create_token("flex-access-token").token

    logger.info("getting link token for user")
    dvla_gen = DVLATokenGenerator(user, logger=logger)
    dvla_wrangler = TokenWrangler(generator=dvla_gen, logger=logger, token_type=TokenType.DVLA)
    dvla_token = dvla_wrangler.get_or_create_token("dvla-linking-token").token

    match_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {flex_token}",
        "x-linking-token": dvla_token
    }
    match_url = f"{FLEX_BASE_URL}/udp/v1/identity/dvla"

    logger.info("Matching tokens")
    match_response = requests.post(match_url, headers=match_headers)
    logger.info(f"Match result = {match_response.status_code}")

    return flex_token


def get_user_data(user: str) -> dict:
    try:
        secretsm = boto3.client("secretsmanager")
        flex_token = secretsm.get_secret_value(SecretId="flex-access-token")
        logger.info("Getting user data")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {flex_token}",
        }
        url = f"{FLEX_BASE_URL}/dvla/v1/customer-summary"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except secretsm.exceptions.ResourceNotFoundException as e:
        logger.error(f"The secret flex-access-token was not found")
        sys.exit()
    except ClientError as e:
        logger.error(f"There was an error retrieving the Flex token: {e}")
        sys.exit()
    except HTTPError as e:
        logger.info(f"Somewhat expected error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error {e}")


if __name__ == "__main__":
    users = {
        "bill": "8bc39b9f-9cdc-4dc6-8364-632d1f7b5916", # has no vehicles
        "belinda": "b32e769a-dd78-48b9-bde4-3b229b9b6c8e", # Has vehicle, untaxed
        "bob": "c3375b6d-e3b8-46c9-895e-e257440b36bc", # Has taxed vehicle
        "bertha": "49fec1c5-0712-4a2d-9116-406eb147ff7a" # Has few vehicles
    }

    try:
        sts = boto3.client("sts")
        sts.get_caller_identity()
    except ClientError as c:
        logger.error(f"Error connecting to AWS account: {str(c)}")
        sys.exit()

    user = users["bob"]
    # flex_token = authenticate_and_match(user)
    data = get_user_data(user)
    print(json.dumps(data, indent=2))