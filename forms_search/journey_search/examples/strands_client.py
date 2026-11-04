# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "strands-agents>=1.53",
#     "truststore>=0.10",
# ]
# ///
"""Try the hosted Journey Search MCP tool from the command line.

A self-contained script: run it with `uv run strands_client.py ...` from any
directory, including on its own outside this repository. See CONNECTING.md.

Settings come from environment variables:

    JOURNEY_SEARCH_MCP_URL        MCP endpoint
    JOURNEY_SEARCH_TOKEN_URL      OAuth token endpoint
    JOURNEY_SEARCH_CLIENT_ID      OAuth client ID
    JOURNEY_SEARCH_CLIENT_SECRET  OAuth client secret
    JOURNEY_SEARCH_SCOPE          OAuth scope (journey-search/search)

Commands:

    uv run strands_client.py tools                      # show the tool and its schemas
    uv run strands_client.py search "report a mosquito" # call the tool directly, no LLM
    uv run strands_client.py agent "I saw an octopus"   # a Strands agent decides when to search

`tools` and `search` need no AWS credentials at all. `agent` runs a model on
Amazon Bedrock, so it needs AWS credentials with Bedrock access in your own
account; Journey Search itself still only needs the OAuth client credentials.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

import truststore

# Verify TLS with the operating system's trust store, so it also works on machines
# with corporate TLS inspection (for example Zscaler). Verification stays on.
truststore.inject_into_ssl()

import httpx
from strands.tools.mcp import MCPClient
from strands.types.exceptions import MCPClientInitializationError

# The client tries to end its MCP session on exit and the platform, which manages
# sessions itself, answers 404. The warning it logs is harmless.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

TOOL_NAME = "search_service_journeys"
SETTINGS = (
    "JOURNEY_SEARCH_MCP_URL",
    "JOURNEY_SEARCH_TOKEN_URL",
    "JOURNEY_SEARCH_CLIENT_ID",
    "JOURNEY_SEARCH_CLIENT_SECRET",
    "JOURNEY_SEARCH_SCOPE",
)


class JourneySearchAuth(httpx.Auth):
    """Adds a Journey Search access token to every request, renewing it before it expires.

    Uses the OAuth client credentials grant. The client secret is only ever sent
    to JOURNEY_SEARCH_TOKEN_URL. The same class is in CONNECTING.md.
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


def journey_search_client(local_url: str | None) -> MCPClient:
    if local_url:
        return MCPClient(url=local_url)
    missing = [name for name in SETTINGS if not os.environ.get(name)]
    if missing:
        sys.exit(f"Set these environment variables first (see CONNECTING.md): {', '.join(missing)}")
    auth = JourneySearchAuth()
    try:
        auth.access_token()  # check the credentials before connecting
    except httpx.HTTPError as exc:
        detail = exc.response.text if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        sys.exit(f"Could not get an access token from JOURNEY_SEARCH_TOKEN_URL: {detail}")
    return MCPClient(url=os.environ["JOURNEY_SEARCH_MCP_URL"], auth_provider=auth)


def show_tools(client: MCPClient) -> None:
    for tool in client.list_tools_sync():
        spec = tool.tool_spec
        print(f"{spec['name']}\n\n{spec['description']}\n")
        print("Input schema:")
        print(json.dumps(spec["inputSchema"]["json"], indent=2))
        if spec.get("outputSchema"):
            print("\nOutput schema:")
            print(json.dumps(spec["outputSchema"]["json"], indent=2))


def search(client: MCPClient, query: str, limit: int) -> None:
    result = client.call_tool_sync(
        tool_use_id="cli", name=TOOL_NAME, arguments={"query": query, "limit": limit}
    )
    if result["status"] != "success":
        sys.exit(f"Tool error: {result['content'][0].get('text', result)}")
    print(json.dumps(result["structuredContent"], indent=2, ensure_ascii=False))


def run_agent(client: MCPClient, message: str, model_id: str, region: str) -> None:
    from strands import Agent
    from strands.models import BedrockModel

    agent = Agent(
        model=BedrockModel(model_id=model_id, region_name=region),
        tools=client.list_tools_sync(),
        system_prompt=(
            "You help citizens use UK government services. Search for service journeys when the "
            "citizen may want to do something a government service could handle. Judge each "
            "candidate yourself, and offer a suitable journey before starting anything."
        ),
        callback_handler=None,
    )
    reply = agent(message)
    for turn in agent.messages:
        for block in turn["content"]:
            if "toolUse" in block:
                print(
                    f"[agent called {block['toolUse']['name']} with {json.dumps(block['toolUse']['input'])}]"
                )
    print(f"\n{reply}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--url", help="Use a local, unauthenticated server instead, e.g. http://127.0.0.1:8000/mcp"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("tools", help="Show the tool's description and schemas")
    search_parser = commands.add_parser("search", help="Call the tool directly, without an LLM")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=5)
    agent_parser = commands.add_parser("agent", help="Let a Strands agent decide when to search")
    agent_parser.add_argument("message")
    agent_parser.add_argument("--model-id", default="eu.anthropic.claude-sonnet-5-5")
    agent_parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-west-2"))
    args = parser.parse_args()

    client = journey_search_client(args.url)
    try:
        client.start()
    except MCPClientInitializationError as exc:
        sys.exit(
            f"Could not connect to Journey Search ({type(exc).__name__}: {exc}). "
            "Check JOURNEY_SEARCH_MCP_URL."
        )
    try:
        if args.command == "tools":
            show_tools(client)
        elif args.command == "search":
            search(client, args.query, args.limit)
        else:
            run_agent(client, args.message, args.model_id, args.region)
    finally:
        client.stop(None, None, None)


if __name__ == "__main__":
    main()
