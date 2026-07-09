from dataclasses import dataclass
from dotenv import dotenv_values
from pathlib import Path
import base64
import hashlib
import secrets
import requests
from bs4 import BeautifulSoup
import pyotp
from urllib.parse import urlparse, parse_qs, urljoin
from agents.src.tools.assets import (
    NoCSRFException,
    NoRedirectURLException,
    NoCodeInURLException,
    TokenExchangeFailedException,
)
from agents.src.tools.assets import get_logger

logger = get_logger()

REDIRECT_URI = "govuk://govuk/login-auth-callback"
MAX_REDIRECT_HOPS = 10


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
    """Loads required environment variables from file."""
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
        email=str(env_vars["PLAYGROUND_EMAIL"]),
        password=str(env_vars["PLAYGROUND_PASSWORD"]),
        totp=str(env_vars["PLAYGROUND_TOTP_SEED"]),
        client_id=str(env_vars["PLAYGROUND_CLIENT_ID"]),
        auth_url=str(env_vars["PLAYGROUND_AUTH_URL"]),
        token_url=str(env_vars["PLAYGROUND_TOKEN_URL"]),
        one_login_env=str(env_vars["PLAYGROUND_ONE_LOGIN_ENV"]),
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
    session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
    if config.attestation_token:
        session.headers.update({"X-Firebase-App-Check": config.attestation_token})
    return session


def make_initial_request(
    session: requests.Session, config: JwtAuthConfig, challenge: str
) -> requests.Response:
    """Makes initial request to Flex Cognito server."""
    query_params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "smoke-test",
        "idpidentifier": "onelogin",
    }

    auth_url = f"https://{config.auth_url}/oauth2/authorize"

    init = session.get(url=auth_url, params=query_params)
    init.raise_for_status()
    return init


def extract_csrf_token(response: requests.Response) -> str:
    soup = BeautifulSoup(response.text, "html.parser")
    csrf_input = soup.find("input", {"name": "_csrf"})
    if not csrf_input:
        raise NoCSRFException("No csrf token in auth response")
    return str(csrf_input["value"])


def post(session: requests.Session, full_path: str, data: dict, token: str):
    """Helper function to make standard posts to OneLogin."""
    payload = {"_csrf": token}
    payload.update(data)
    res = session.post(full_path, data=payload)
    res.raise_for_status()
    return res


def get_onelogin_oauth_code(
    session: requests.Session, config: JwtAuthConfig, csrf_token: str
) -> str:
    env_name = config.one_login_env
    if env_name == "production":
        onelogin_domain = "signin.account.gov.uk"
    else:
        onelogin_domain = f"signin.{env_name}.account.gov.uk"

    base_url = f"https://{onelogin_domain}"

    logger.info("Posting form data to OneLogin...")

    post(session, f"{base_url}/sign-in-or-create", {}, csrf_token)
    post(session, f"{base_url}/enter-email?", {"email": config.email}, csrf_token)
    post(
        session, f"{base_url}/enter-password", {"password": config.password}, csrf_token
    )

    totp = pyotp.TOTP(config.totp)
    otp = totp.now()

    logger.info("Posting OTP value...")

    totp_payload = {"_csrf": csrf_token, "code": otp}
    ol_response = session.post(
        f"{base_url}/enter-authenticator-app-code?",
        data=totp_payload,
        allow_redirects=False,
    )

    code_redirect_url = None

    for _ in range(MAX_REDIRECT_HOPS):
        if ol_response.status_code not in (301, 302, 303, 307, 308):
            break
        location = urljoin(ol_response.url, ol_response.headers["Location"])
        if urlparse(location).scheme not in ("http", "https"):
            code_redirect_url = location
            break
        ol_response = session.get(location, allow_redirects=False)

    if not code_redirect_url:
        raise NoRedirectURLException("OneLogin did not return a redirect url after OTP")

    logger.info("Extracting code from redirect URL")

    parsed_url = urlparse(code_redirect_url)
    qs = parse_qs(parsed_url.query)
    code = qs.get("code", [None])[0]

    if not code:
        raise NoCodeInURLException("No code found in redirect url")

    return code


def get_access_token(config: JwtAuthConfig, code: str, verifier: str) -> str:
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
        "scope": "email openid",
    }

    token_url = f"https://{config.token_url}/oauth2/token"

    logger.info("Requesting token...")
    token_response = requests.post(
        token_url,
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if not token_response.ok:
        raise TokenExchangeFailedException(
            f"Token exchange failed: {token_response.text}"
        )

    return token_response.json().get("access_token")


def main():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    logger.info("Generating token from provided environment variables")
    logger.info("Loading config...")
    config = load_config(env_path=env_path)

    try:
        logger.info("Creating PKCE pair...")
        verifier, challenge = generate_pkce_pair()
        logger.info("Creating HTTP session...")
        session = make_session(config=config)
        logger.info("Making initial call to Cognito...")
        initial = make_initial_request(
            session=session, config=config, challenge=challenge
        )
        logger.info("Getting CSRF token...")
        csrf_token = extract_csrf_token(initial)
        logger.info("Calling OneLogin...")
        one_login_code = get_onelogin_oauth_code(
            session=session, config=config, csrf_token=csrf_token
        )
        logger.info("Calling Cognito for access token")
        access_token = get_access_token(
            config=config, code=one_login_code, verifier=verifier
        )
        print(access_token)
    except RuntimeError:
        logger.error("Config load failed")
        raise
    except NoCSRFException:
        logger.error("No code from auth server")
        raise
    except NoCodeInURLException, NoRedirectURLException:
        logger.error("OneLogin response failed")
        raise
    except TokenExchangeFailedException:
        logger.error("Final token exchange error")
        raise
    except Exception as e:
        logger.error("Unexpected error %s", str(e))
        raise


if __name__ == "__main__":
    main()
