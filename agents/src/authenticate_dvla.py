import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin
import sys


def get_dvla_linking_token(customer_id: str) -> str:
    base_url = "https://architecture-link-account-service-ui-ext.dvla.gov.uk"

    session = requests.Session()

    # Standard headers to act like a normal browser
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
    )

    # 1. INITIATE THE FLOW
    # This sets up the OAuth session state
    # in the backend and redirects us to the pre-filled stub form.
    init_url = f"{base_url}/create-token?locale=en"
    print(f"Initiating flow at {init_url}...")
    response = session.get(init_url)
    response.raise_for_status()

    # We should now have landed on the /auth/stubgeneric... page
    print(f"Landed on stub form: {response.url}")

    # 2. Extract form from the page we landed on
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form", action="/auth/stubgeneric/callback")
    if not form:
        raise RuntimeError(
            f"Could not find the stub login form. Landed on {response.url}"
        )

    # 3. Scrape the pre-filled payload
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
                payload[name] = first_option.get("value", "") if first_option else ""
        elif input_tag.get("type") in ["radio", "checkbox"]:
            if input_tag.has_attr("checked"):
                payload[name] = input_tag.get("value", "")
        else:
            payload[name] = input_tag.get("value", "")

    # 4. Inject the specific customer ID
    print(f"Injecting customer_id: {customer_id}")
    payload["customer_id"] = customer_id

    # Update the Referer dynamically based on where the form actually lives
    session.headers.update({"Referer": response.url})

    # 5. Submit the form and trace the redirects
    print("Submitting form to callback...")
    post_url = urljoin(base_url, str(form["action"]))
    response = session.post(post_url, data=payload, allow_redirects=False)

    token_redirect_url = None

    while response.is_redirect:
        next_url = response.headers.get("Location")
        if not next_url:
            break

        if next_url.startswith("govuk://"):
            token_redirect_url = next_url
            break

        next_url = urljoin(base_url, next_url)
        response = session.get(next_url, allow_redirects=False)

    if not token_redirect_url:
        raise RuntimeError(
            f"Did not reach the govuk:// redirect. Stopped at {response.status_code} {response.url}\nResponse text: {response.text[:500]}"
        )

    print("Extracting token from redirect URI...")
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
        linking_token = get_dvla_linking_token(target_id)
        print("\n--------------------------------------------------")
        print("Token Retrieved Successfully:\n")
        print(linking_token)
        print("--------------------------------------------------\n")
    except Exception as e:
        print(f"\nError: {e}")
