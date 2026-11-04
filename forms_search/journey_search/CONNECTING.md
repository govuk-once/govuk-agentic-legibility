# Connecting to Journey Search

For teams calling Journey Search from their own agent, such as the GOV.UK
orchestrating agent.

Journey Search is a hosted MCP server with one tool, `search_service_journeys`.
Give it a plain-language description of what a citizen wants to do and it
returns a ranked shortlist of GOV.UK service journeys that might fit. It
implements the Journey Search Contract RFC.

You need OAuth client credentials from the Agentic Legibility team. You do not
need access to our AWS account.

## What you'll receive

| Setting | Value |
|---|---|
| `JOURNEY_SEARCH_MCP_URL` | `https://bedrock-agentcore.eu-west-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aeu-west-2%3A971089639546%3Aruntime%2Fjourney_search-utXMK5Hk2w/invocations?qualifier=DEFAULT` |
| `JOURNEY_SEARCH_TOKEN_URL` | `https://journey-search-971089639546.auth.eu-west-2.amazoncognito.com/oauth2/token` |
| `JOURNEY_SEARCH_CLIENT_ID` | `v9l8tn9uis6tir3q6k1q4nsqv` |
| `JOURNEY_SEARCH_CLIENT_SECRET` | Sent to you separately, through a secure channel |
| `JOURNEY_SEARCH_SCOPE` | `journey-search/search` |

These are the values for the shared integration-test service in eu-west-2.
Only the client secret is sensitive: keep it out of source control and logs.

## Check your access

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and the
example client,
[`examples/strands_client.py`](examples/strands_client.py). It's a single file
that declares its own dependencies, so it runs from any directory with no
other setup. Save it, then:

```bash
export JOURNEY_SEARCH_MCP_URL='<value from the table>'
export JOURNEY_SEARCH_TOKEN_URL='<value from the table>'
export JOURNEY_SEARCH_CLIENT_ID='<value from the table>'
export JOURNEY_SEARCH_CLIENT_SECRET='<the secret we sent you>'
export JOURNEY_SEARCH_SCOPE='journey-search/search'

uv run strands_client.py tools                        # the tool's description and schemas
uv run strands_client.py search "report a mosquito"   # call the tool directly
```

`tools` and `search` need no AWS credentials and no LLM. `search` prints:

```json
{
  "candidates": [
    {
      "workflow_id": "3652",
      "title": "Report a mosquito",
      "description": "Report a mosquito found in the UK to UKHSA, giving the collection date, location, ..."
    },
    ...
  ]
}
```

To see an agent decide for itself when to search:

```bash
uv run strands_client.py agent "I was diving near Plymouth and spotted an octopus!"
```

This runs a Claude model on Amazon Bedrock, so it needs AWS credentials with
Bedrock access in your own account (`--model-id` and `--region` change the
model). Journey Search itself still uses only the OAuth credentials.

## Add it to your Strands agent

Requires `strands-agents` 1.53 or later.

```python
import os
import time

import httpx
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient


class JourneySearchAuth(httpx.Auth):
    """Adds a Journey Search access token to every request, renewing it before it expires.

    Uses the OAuth client credentials grant. The client secret is only ever sent
    to JOURNEY_SEARCH_TOKEN_URL.
    """

    def __init__(self) -> None:
        self.token, self.expires_at = "", 0.0

    def access_token(self) -> str:
        if time.time() > self.expires_at - 60:
            response = httpx.post(
                os.environ["JOURNEY_SEARCH_TOKEN_URL"],
                data={"grant_type": "client_credentials", "scope": os.environ["JOURNEY_SEARCH_SCOPE"]},
                auth=(os.environ["JOURNEY_SEARCH_CLIENT_ID"], os.environ["JOURNEY_SEARCH_CLIENT_SECRET"]),
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
            self.token, self.expires_at = body["access_token"], time.time() + body["expires_in"]
        return self.token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.access_token()}"
        yield request


auth = JourneySearchAuth()
auth.access_token()  # check the credentials now, so a mistake fails here with a clear error

journey_search = MCPClient(url=os.environ["JOURNEY_SEARCH_MCP_URL"], auth_provider=auth)

with journey_search:
    agent = Agent(
        model=BedrockModel(model_id="eu.anthropic.claude-sonnet-5-5", region_name="eu-west-2"),  # your model
        tools=journey_search.list_tools_sync(),  # add your other tools here
    )
    agent("I was diving near Plymouth and spotted an octopus!")
```

Every request carries a current token: `JourneySearchAuth` gets one with the
OAuth client credentials grant and gets a new one shortly before it expires
(tokens last an hour), so long-running agents don't need to reconnect.

Things to know:

- **Why not Strands' `MCPClientCredentials`?** It also works, but it finds
  the token endpoint through the MCP server's metadata, so the server decides
  where your client secret is sent, and the `mcp` library warns that this
  will stop working in `mcp` 3.0. The code above only ever sends the secret to
  the token URL you configure.

- **Keep the connection open while you use it.** Each new MCP session can
  start a new server instance, which adds a cold start of a few seconds. A
  search on an open connection takes around 300 ms on our side.
- **"Session termination failed: 404" is harmless.** On exit the client tries
  to end its MCP session; the hosting platform manages sessions itself and
  says no. You can silence it with
  `logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)`.
- **Corporate TLS inspection.** On laptops behind something like Zscaler,
  Python can reject certificates that browsers and `curl` accept (you'll see
  `CERTIFICATE_VERIFY_FAILED`). Install `truststore` and call
  `truststore.inject_into_ssl()` at startup, which verifies certificates with
  the operating system's trust store. Don't turn verification off.
  `strands_client.py` already does this.

We've tested this with `strands-agents` 1.53.0 (with `mcp` 1.30.0), 1.55.0
(`mcp` 2.1.1) and 1.64.0 (`mcp` 2.3.0).

## Without Strands

Any MCP client that supports streamable HTTP can connect: get a token with the
client credentials grant and send `Authorization: Bearer <token>` with every
request. To try it with `curl`, with the settings exported as above:

```bash
TOKEN=$(curl -s -X POST "$JOURNEY_SEARCH_TOKEN_URL" \
  -u "$JOURNEY_SEARCH_CLIENT_ID:$JOURNEY_SEARCH_CLIENT_SECRET" \
  -d grant_type=client_credentials -d scope="$JOURNEY_SEARCH_SCOPE" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -s -X POST "$JOURNEY_SEARCH_MCP_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "search_service_journeys",
                  "arguments": {"query": "report a mosquito", "limit": 2}}}'
```

## The tool

`search_service_journeys(query: str, limit: int = 5)`

| Argument | Meaning |
|---|---|
| `query` | Plain-language description of what the citizen wants to do, for example "change my redundancy claim for unpaid holiday". Up to 1,000 characters. Don't include the citizen's personal details. |
| `limit` | Maximum number of candidates, 5 by default. Values above 20 are reduced to 20. |

It returns `{"candidates": [{"workflow_id", "title", "description"}, ...]}`,
ranked most likely first. The tool's description, which your model sees, says
the same things as the section below.

## Using the results

As set out in the RFC, Journey Search only retrieves candidates. Your agent
decides what to do with them.

- **Candidates are not confirmed matches.** Search favours recall over
  precision, so some candidates will be irrelevant, and it always returns up
  to `limit` candidates even when none fits. Judge every candidate, even when
  only one is returned.
- **Then choose:** offer the journey that fits, ask the citizen which applies
  if several could, or use another capability if none does. You can choose
  from candidates you already have without searching again.
- **Searching doesn't start anything.** Starting a journey is a separate call
  to Legibility's execution interface, and should happen only after the
  citizen agrees.
- **Search when the citizen might want to do something a government form
  could handle**, including unusual things such as reporting an octopus
  sighting. It isn't for general information questions, and you don't need
  to search on every turn.
- **Each call is independent.** Journey Search keeps no state, so put
  everything relevant from the conversation in the query.

## Errors

| What you see | Meaning | What to do |
|---|---|---|
| `HTTPStatusError: Client error '400 Bad Request'` from the token URL, or `invalid_client` | Wrong client ID or secret | Check `JOURNEY_SEARCH_CLIENT_ID` and `JOURNEY_SEARCH_CLIENT_SECRET` |
| `400` `invalid_scope` from the token URL | Wrong scope | Use `journey-search/search` |
| `401` `Missing Authentication Token` | No `Authorization` header | Send `Authorization: Bearer <token>` |
| `401` `Token has expired` (or another token error) | Token expired, malformed or from the wrong client | Get a new token |
| Tool error `query must not be empty` (or too long) | Invalid argument | Fix the query |
| Tool error `Journey search is temporarily unavailable` | A problem on our side | Retry shortly; tell us if it persists |

Tool errors come back as MCP tool results with `isError: true`, so your model
sees them and can retry or explain.
