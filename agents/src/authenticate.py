from dataclasses import dataclass
from dotenv import dotenv_values
from pathlib import Path
import logging
import base64
import hashlib
import secrets
import requests


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)

REDIRECT_URI = "govuk://govuk/login-auth-callback"


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


def load_config(env_path: Path) -> JwtAuthConfig:
    """Loads required environment variables from file.

    This loads the list of required variables (specified above) from a file into the run environment.

    Args:
        env_path: (Path) The path to the file

    Returns:
        (JwtAuthConfig)

    Raises:
        FileNotFoundError: if environment file is not found
        RuntimeError: if any environment variables are missing or malformed

    """
    if env_path.is_file():
        env_vars = dotenv_values(env_path)
    else:
        raise FileNotFoundError(f"File path {env_path} does not exist")

    required = [
        "PLAYGROUND_EMAIL",
        "PLAYGROUND_PASSWORD",
        "PLAYGROUND_TOTP_SEED",
        "PLAYGROUND_CLIENT_ID",
        "PLAYGROUND_AUTH_URL",
        "PLAYGROUND_TOKEN_URL",
        "PLAYGROUND_ONE_LOGIN_ENV",
    ]

    missing = [var for var in required if not env_vars.get(var)]
    if missing:
        for missing_var in missing:
            logger.error("Environment variable %s is required but not set", missing_var)
        raise RuntimeError("One or more missing environment variables")
    if "@" not in (env_vars.get("PLAYGROUND_EMAIL") or ""):
        logger.error("PLAYGROUND_EMAIL must be a valid email address")
        raise RuntimeError("Invalid Email address")

    return JwtAuthConfig(
        email=env_vars["PLAYGROUND_EMAIL"],
        password=env_vars["PLAYGROUND_PASSWORD"],
        totp=env_vars["PLAYGROUND_TOTP_SEED"],
        client_id=env_vars["PLAYGROUND_CLIENT_ID"],
        auth_url=env_vars["PLAYGROUND_AUTH_URL"],
        token_url=env_vars["PLAYGROUND_TOKEN_URL"],
        one_login_env=env_vars["PLAYGROUND_ONE_LOGIN_ENV"],
    )


def generate_pkce_pair() -> tuple[str, str]:
    """Generates a pair used to verify the first and last calls to the token server are from the same source."""
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def make_session(config: JwtAuthConfig) -> requests.Session:
    "Makes HTTP session capable of holding persistent cookies."
    session = requests.Session()
    session.headers.update(
        {"Content-Type": "application/x-www-form-urlencoded"}
    )
    if config.attestation_token:
        session.headers.update(
            {"X-Firebase-App-Check": config.attestation_token}
        )
    return session


def make_initial_request(config: JwtAuthConfig, challenge: str) -> requests.Response:
    session = make_session(config=config)
    query_params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "smoke-test",
        "idpidentifier": "onelogin"
    }

    auth_url = f"https://{config.auth_url}/oauth2/authorize"
    
    init = session.get(url=auth_url, params=query_params)
    init.raise_for_status()
    return init




