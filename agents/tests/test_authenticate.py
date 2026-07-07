import pytest
from src.authenticate import load_config, JwtAuthConfig, REDIRECT_URI
from pathlib import Path


@pytest.mark.describe("Config loading")
class TestConfigLoading:
    @pytest.mark.it("Correctly loads valid file to data class")
    def test_correctly_loads_valid_file(self):
        file_path = Path(__file__).parent.resolve() / "resources" / ".validenv"
        config = load_config(file_path)
        assert isinstance(config, JwtAuthConfig)
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
        assert config == expected

    @pytest.mark.it("Spots missing or malformed variables and raises error")
    def test_spot_invalid_env_var_file(self, caplog):
        file_path = Path(__file__).parent.resolve() / "resources" / ".badenv1"
        with pytest.raises(RuntimeError):
            load_config(file_path)
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
            load_config(file_path)
        assert "PLAYGROUND_EMAIL must be a valid email address" in caplog.text
