"""Example: a Strands agent using the hosted Journey Search MCP tool.

The caller needs only OAuth client credentials for the Journey Search user
pool, not AWS credentials for our account. It exchanges them for a short-lived
access token and sends it as a Bearer token with every MCP request.

    export JOURNEY_SEARCH_MCP_URL=...       # stack output McpUrl
    export JOURNEY_SEARCH_TOKEN_URL=...     # stack output TokenUrl
    export JOURNEY_SEARCH_SCOPE=...         # stack output Scope
    export JOURNEY_SEARCH_CLIENT_ID=...     # stack output ClientId
    export JOURNEY_SEARCH_CLIENT_SECRET=... # shared separately

    # Call the tool directly, without an LLM (so no AWS credentials at all):
    uv run --group client python examples/strands_client.py --direct "report a mosquito"

    # Let a Strands agent decide when to search. The agent's own model needs
    # Bedrock access in the caller's account; Journey Search does not.
    uv run --group client python examples/strands_client.py "I spotted an octopus while diving"

    # A local server (no auth): uv run journey-search-server
    uv run --group client python examples/strands_client.py --url http://127.0.0.1:8000/mcp --direct "report a mosquito"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient


def access_token() -> str:
    """OAuth 2.0 client credentials grant against the Journey Search user pool."""
    response = httpx.post(
        os.environ["JOURNEY_SEARCH_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": os.environ["JOURNEY_SEARCH_SCOPE"]},
        auth=(os.environ["JOURNEY_SEARCH_CLIENT_ID"], os.environ["JOURNEY_SEARCH_CLIENT_SECRET"]),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def journey_search_client(url: str, token: str | None) -> MCPClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # AgentCore manages MCP sessions itself and doesn't accept the client's session DELETE.
    return MCPClient(
        lambda: streamablehttp_client(url, headers=headers, timeout=30, terminate_on_close=False)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("message", help="A search query (with --direct) or a citizen's message")
    parser.add_argument(
        "--direct", action="store_true", help="Call the tool directly instead of via an agent"
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--url", default=os.environ.get("JOURNEY_SEARCH_MCP_URL"))
    args = parser.parse_args()
    if not args.url:
        sys.exit("Set JOURNEY_SEARCH_MCP_URL or pass --url")

    local = args.url.startswith("http://127.0.0.1") or args.url.startswith("http://localhost")
    client = journey_search_client(args.url, None if local else access_token())

    with client:
        if args.direct:
            result = client.call_tool_sync(
                tool_use_id="example",
                name="search_service_journeys",
                arguments={"query": args.message, "limit": args.limit},
            )
            print(json.dumps(result.get("structuredContent") or result, indent=2, ensure_ascii=False))
            return

        from strands import Agent

        agent = Agent(
            tools=client.list_tools_sync(),
            system_prompt=(
                "You help citizens use UK government services. Search for service journeys when the "
                "citizen may want to do something a government service could handle. Judge each "
                "candidate yourself. Offer a suitable journey before starting anything."
            ),
        )
        agent(args.message)


if __name__ == "__main__":
    main()
