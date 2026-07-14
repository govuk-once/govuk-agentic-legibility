import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin
import sys
import logging
from agents.src.tools.assets import get_logger, TokenGenerator, TokenWrangler, TokenType
import boto3
from botocore.exceptions import ClientError

logger = get_logger()

SECRET_ID = "dvla-linking-token"  # nosec


class DVLATokenGenerator(TokenGenerator):
    def __init__(self, customer_id: str, logger: logging.Logger) -> None:
        self.customer_id = customer_id
        self.session = requests.Session()
        self.logger = logger
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
        )
        self.base_url = "https://architecture-link-account-service-ui-ext.dvla.gov.uk"

    def generate_new_token(self) -> str:
        init_url = f"{self.base_url}/create-token?locale=en"
        self.logger.info(f"Initiating flow at {init_url}...")
        response = self.session.get(init_url)
        response.raise_for_status()

        self.logger.info(f"Landed on stub form: {response.url}")

        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form", action="/auth/stubgeneric/callback")
        if not form:
            raise RuntimeError(
                f"Could not find the stub login form. Landed on {response.url}"
            )

        payload = {}
        for input_tag in form.find_all(["input", "select"]):
            name = input_tag.get("name")
            if not name:
                continue

            if input_tag.name == "select":
                selected = input_tag.find("option", selected=True)
                if selected:
                    payload[name] = selected.get("value", "")
                else:
                    first_option = input_tag.find("option")
                    payload[name] = (
                        first_option.get("value", "") if first_option else ""
                    )
            elif input_tag.get("type") in ["radio", "checkbox"]:
                if input_tag.has_attr("checked"):
                    payload[name] = input_tag.get("value", "")
            else:
                payload[name] = input_tag.get("value", "")

        self.logger.info(f"Injecting customer_id: {self.customer_id}")
        payload["customer_id"] = self.customer_id

        self.session.headers.update({"Referer": response.url})

        self.logger.info("Submitting form to callback...")
        post_url = urljoin(self.base_url, str(form["action"]))
        response = self.session.post(post_url, data=payload, allow_redirects=False)

        token_redirect_url = None

        while response.is_redirect:
            next_url = response.headers.get("Location")
            if not next_url:
                break

            if next_url.startswith("govuk://"):
                token_redirect_url = next_url
                break

            next_url = urljoin(self.base_url, next_url)
            response = self.session.get(next_url, allow_redirects=False)

        if not token_redirect_url:
            raise RuntimeError(
                f"Did not reach the govuk:// redirect. Stopped at {response.status_code} {response.url}\nResponse text: {response.text[:500]}"
            )

        self.logger.info("Extracting token from redirect URI...")
        parsed_url = urlparse(token_redirect_url)
        qs = parse_qs(parsed_url.query)
        token = qs.get("token", [None])[0]

        if not token:
            raise RuntimeError(
                "Redirect URL reached, but 'token' query parameter is missing."
            )

        return token


if __name__ == "__main__":
    target_id = sys.argv[1]
    try:
        sts = boto3.client("sts")
        sts.get_caller_identity()
    except ClientError as c:
        logger.error(f"Error connecting to AWS account: {str(c)}")
        sys.exit(1)
    generator = DVLATokenGenerator(customer_id=target_id, logger=logger)
    wrangler = TokenWrangler(
        generator=generator, logger=logger, token_type=TokenType.DVLA
    )
    token_result = wrangler.get_or_create_token(SECRET_ID)
    print(token_result)
