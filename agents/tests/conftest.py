import pytest
from src.authenticate import JwtAuthConfig

@pytest.fixture(scope="class")
def sample_config():
    return JwtAuthConfig(
            email="joe.bloggs@digital.cabinet-office.gov.uk",
            password="pa55word",
            totp="NSGHGGSKKHG74753MFDNDG",
            client_id="733jnfdgyye774hjn",
            auth_url="woo.foo.bar.auth.com",
            token_url="woo.foo.bar.token.com",
            one_login_env="test",
            redirect_uri="http://boo.foo.com",
            attestation_token=None,
        )