import pytest
from agents.src.tools.authenticate_flex import (
    FlexTokenGenerator,
    requests,
)
from agents.src.tools.assets import get_logger, JwtAuthConfig, REDIRECT_URI
from pathlib import Path
import hashlib
import base64
from unittest.mock import patch

test_logger = get_logger()


@pytest.mark.describe("FlexTokenGenerator")
class TestFlexTokenGenerator:
    @pytest.mark.it("Correctly loads valid file to data class")
    def test_correctly_loads_valid_file(self):
        file_path = Path(__file__).parent.resolve() / "resources" / ".validenv"
        generator = FlexTokenGenerator(env_path=file_path, logger=test_logger)
        assert isinstance(generator.config, JwtAuthConfig)
        expected = JwtAuthConfig(
            email="joe.bloggs@digital.cabinet-office.gov.uk",
            password="pa55word",
            totp="NSGHGGSKKHG74753MFDNDG",
            client_id="733jnfdgyye774hjn",
            auth_url="woo.foo.bar.auth.com",
            token_url="woo.foo.bar.token.com",
            one_login_env="test",
            redirect_uri=REDIRECT_URI,
            attestation_token=None,
        )
        assert generator.config == expected

    @pytest.mark.it("Spots missing or malformed variables and raises error")
    def test_spot_invalid_env_var_file(self, caplog):
        file_path = Path(__file__).parent.resolve() / "resources" / ".badenv1"
        with pytest.raises(RuntimeError):
            FlexTokenGenerator(env_path=file_path, logger=test_logger)
        assert (
            "Environment variable PLAYGROUND_AUTH_URL is required but not set"
            in caplog.text
        )
        assert (
            "Environment variable PLAYGROUND_TOTP_SEED is required but not set"
            in caplog.text
        )

    @pytest.mark.it("Spots malformed email address")
    def test_spot_malformed_email_address(self, caplog):
        file_path = Path(__file__).parent.resolve() / "resources" / ".badenv2"
        with pytest.raises(RuntimeError):
            FlexTokenGenerator(env_path=file_path, logger=test_logger)
        assert "PLAYGROUND_EMAIL must be a valid email address" in caplog.text

    @pytest.mark.it("PKCE returns a tuple of strings")
    def test_returns_strings(self):
        v, c = FlexTokenGenerator.generate_pkce_pair()
        assert isinstance(v, str)
        assert isinstance(c, str)

    @pytest.mark.it("PKCE has no padding")
    def test_no_padding(self):
        v, c = FlexTokenGenerator.generate_pkce_pair()
        assert "=" not in v
        assert "=" not in c

    @pytest.mark.it("PKCE correctly works as a challenge pair")
    def test_correct_pair(self):
        v, c = FlexTokenGenerator.generate_pkce_pair()
        expected_digest = hashlib.sha256(v.encode("utf-8")).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(expected_digest).decode("utf-8").rstrip("=")
        )
        assert c == expected_challenge

    @pytest.mark.it("makes request with correct parameters and url")
    @patch.object(requests.Session, "get")
    def test_makes_correct_request(self, req):
        file_path = Path(__file__).parent.resolve() / "resources" / ".validenv"
        generator = FlexTokenGenerator(env_path=file_path, logger=test_logger)
        generator._make_initial_request(challenge="XXYY")
        expected_url = "https://woo.foo.bar.auth.com/oauth2/authorize"
        expected_params = {
            "client_id": "733jnfdgyye774hjn",
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "openid email",
            "code_challenge": "XXYY",
            "code_challenge_method": "S256",
            "state": "smoke-test",
            "idpidentifier": "onelogin",
        }
        req.assert_called_once_with(url=expected_url, params=expected_params)
