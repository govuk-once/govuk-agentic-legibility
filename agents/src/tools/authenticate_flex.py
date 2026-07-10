from dotenv import dotenv_values
from pathlib import Path
import time
import base64
import hashlib
import secrets
import logging
import sys
import requests
from bs4 import BeautifulSoup
import pyotp
import jwt
from urllib.parse import urlparse, parse_qs, urljoin
from agents.src.tools.assets import (
    NoCSRFException,
    NoRedirectURLException,
    NoCodeInURLException,
    TokenExchangeFailedException,
    get_logger,
    get_secret, get_secrets_client, TokenGenerator, JwtAuthConfig, write_secret, TokenWrangler, TokenType
)
import boto3
from botocore.exceptions import ClientError


logger = get_logger()

MAX_REDIRECT_HOPS = 10
SECRET_ID = "flex-access-token"


class FlexTokenGenerator(TokenGenerator):
    """Carries out the Flex authentication procedure and retrieves a JWT."""

    def __init__(self, env_path: Path, logger: logging.Logger) -> None:
        self.env_path = env_path
        self.logger = logger
        self.logger.info("Loading config...")
        self.config: JwtAuthConfig = self._load_config()
        self.logger.info("Creating HTTP session...")
        self.session: requests.Session = self._make_session()

    def _load_config(self) -> JwtAuthConfig:
        """Loads required environment variables from file."""
        if self.env_path.is_file():
            env_vars = dotenv_values(self.env_path)
        else:
            raise FileNotFoundError(f"File path {self.env_path} does not exist")

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
                self.logger.error("Environment variable %s is required but not set", missing_var)
            raise RuntimeError("One or more missing environment variables")
        if "@" not in (env_vars.get("PLAYGROUND_EMAIL") or ""):
            self.logger.error("PLAYGROUND_EMAIL must be a valid email address")
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


    @classmethod
    def generate_pkce_pair(cls) -> tuple[str, str]:
        """Generates a pair used to verify the first and last calls to the token server are from the same source."""
        verifier_bytes = secrets.token_bytes(32)
        verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return verifier, challenge

    def _make_session(self) -> requests.Session:
        "Makes HTTP session capable of holding persistent cookies."
        session = requests.Session()
        session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        if self.config and self.config.attestation_token:
            session.headers.update({"X-Firebase-App-Check": self.config.attestation_token})
        return session


    def _make_initial_request(self, challenge: str) -> requests.Response:
        """Makes initial request to Flex Cognito server."""
        query_params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "scope": "openid email",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "smoke-test",
            "idpidentifier": "onelogin",
        }

        auth_url = f"https://{self.config.auth_url}/oauth2/authorize"

        init = self.session.get(url=auth_url, params=query_params)
        init.raise_for_status()
        return init


    def _extract_csrf_token(self, response: requests.Response) -> str:
        """Extracts CSRF token from OneLogin response."""
        soup = BeautifulSoup(response.text, "html.parser")
        csrf_input = soup.find("input", {"name": "_csrf"})
        if not csrf_input:
            raise NoCSRFException("No csrf token in auth response")
        return str(csrf_input["value"])


    def _post(self, full_path: str, data: dict, token: str):
        """Helper function to make standard posts to OneLogin."""
        payload = {"_csrf": token}
        payload.update(data)
        res = self.session.post(full_path, data=payload)
        res.raise_for_status()
        return res


    def _get_onelogin_oauth_code(self, csrf_token: str) -> str:
        """Get OneLogin authorisation code."""
        env_name = self.config.one_login_env
        if env_name == "production":
            onelogin_domain = "signin.account.gov.uk"
        else:
            onelogin_domain = f"signin.{env_name}.account.gov.uk"

        base_url = f"https://{onelogin_domain}"

        self.logger.info("Posting form data to OneLogin...")

        self._post(f"{base_url}/sign-in-or-create", {}, csrf_token)
        self._post(f"{base_url}/enter-email?", {"email": self.config.email}, csrf_token)
        self._post(
            f"{base_url}/enter-password", {"password": self.config.password}, csrf_token
        )

        totp = pyotp.TOTP(self.config.totp)
        otp = totp.now()

        self.logger.info("Posting OTP value...")

        totp_payload = {"_csrf": csrf_token, "code": otp}
        ol_response = self.session.post(
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
            ol_response = self.session.get(location, allow_redirects=False)

        if not code_redirect_url:
            raise NoRedirectURLException("OneLogin did not return a redirect url after OTP")

        self.logger.info("Extracting code from redirect URL")

        parsed_url = urlparse(code_redirect_url)
        qs = parse_qs(parsed_url.query)
        code = qs.get("code", [None])[0]

        if not code:
            raise NoCodeInURLException("No code found in redirect url")

        return code


    def _get_access_token(self, code: str, verifier: str) -> str:
        """Retrieve JWT from Flex/Cognito."""
        token_payload = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "code_verifier": verifier,
            "scope": "email openid",
        }

        token_url = f"https://{self.config.token_url}/oauth2/token"

        self.logger.info("Requesting token...")
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
    
    def generate_new_token(self) -> str | None:
        self.logger.info("Generating token from provided environment variables")

        try:
            self.logger.info("Creating PKCE pair...")
            verifier, challenge = FlexTokenGenerator.generate_pkce_pair()
            
            self.logger.info("Making initial call to Cognito...")
            initial = self._make_initial_request(challenge=challenge)
            self.logger.info("Getting CSRF token...")
            csrf_token = self._extract_csrf_token(initial)
            self.logger.info("Calling OneLogin...")
            one_login_code = self._get_onelogin_oauth_code(csrf_token=csrf_token)
            self.logger.info("Calling Cognito for access token")
            access_token = self._get_access_token(code=one_login_code, verifier=verifier)
            return access_token
        except RuntimeError:
            self.logger.error("Config load failed")
            raise
        except NoCSRFException:
            self.logger.error("No code from auth server")
            raise
        except NoCodeInURLException, NoRedirectURLException:
            self.logger.error("OneLogin response failed")
            raise
        except TokenExchangeFailedException:
            self.logger.error("Final token exchange error")
            raise
        except Exception as e:
            self.logger.error("Unexpected error %s", str(e))
            raise



        
    


if __name__ == "__main__":
    try:
        sts = boto3.client("sts")
        sts.get_caller_identity()
    except ClientError as c:
        logger.error(f"Error connecting to AWS account: {str(c)}")
        sys.exit()
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    generator = FlexTokenGenerator(env_path=env_path, logger=logger)
    wrangler = TokenWrangler(generator=generator, logger=logger, token_type=TokenType.FLEX)
    token_result = wrangler.get_or_create_token(SECRET_ID)
    print(token_result)
