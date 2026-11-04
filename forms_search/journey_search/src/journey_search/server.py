"""MCP server exposing ``search_service_journeys``: a thin wrapper around JourneySearch.

Runs streamable HTTP in stateless mode at ``/mcp`` on port 8000, which is what
Amazon Bedrock AgentCore Runtime expects of an MCP container. Authentication
happens before requests reach the container (AgentCore's JWT authorizer), so
the server itself is unauthenticated and binds to localhost unless
``JOURNEY_SEARCH_HOST`` says otherwise (the container sets ``0.0.0.0``).

Query text is not logged by default because citizens' messages may contain
personal details; set ``JOURNEY_SEARCH_LOG_QUERIES=true`` to log it in development.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Annotated

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from journey_search.config import Settings
from journey_search.contract import (
    DEFAULT_LIMIT,
    LIMIT_DESCRIPTION,
    QUERY_DESCRIPTION,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    SearchResponse,
    clamp_limit,
)
from journey_search.search import JourneySearch, build_search

logger = logging.getLogger("journey_search")


def log_event(**fields: object) -> None:
    """One JSON object per line, which CloudWatch Logs Insights can query directly."""
    logger.info(json.dumps(fields, default=str))


def create_server(
    search: JourneySearch,
    host: str = "127.0.0.1",
    port: int = 8000,
    log_queries: bool = False,
) -> FastMCP:
    server = FastMCP(
        name="journey-search",
        instructions="Finds GOV.UK service journeys a citizen might complete. Results are candidates only.",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    started_at = int(time.time())

    @server.tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Search service journeys",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def search_service_journeys(
        query: Annotated[str, Field(description=QUERY_DESCRIPTION)],
        limit: Annotated[int, Field(description=LIMIT_DESCRIPTION, ge=1)] = DEFAULT_LIMIT,
    ) -> SearchResponse:
        began = time.perf_counter()
        event: dict[str, object] = {"event": "search", "query_chars": len(query), "limit": clamp_limit(limit)}
        if log_queries:
            event["query"] = query
        try:
            # boto3 is blocking, so keep it off the event loop.
            result = await anyio.to_thread.run_sync(search.search, query, limit)
        except ValueError as exc:
            log_event(**event, outcome="invalid", error=str(exc))
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            log_event(**event, outcome="error", error_type=type(exc).__name__)
            logger.exception("search failed")
            raise ToolError("Journey search is temporarily unavailable. Try again shortly.") from exc
        log_event(
            **event,
            outcome="ok",
            candidates=len(result.candidates),
            latency_ms=round((time.perf_counter() - began) * 1000),
        )
        return result

    @server.custom_route("/ping", methods=["GET"])
    async def ping(request: Request) -> JSONResponse:
        # AgentCore uses this for health. time_of_last_update must only change when the
        # status changes, or idle sessions are never released.
        return JSONResponse({"status": "Healthy", "time_of_last_update": started_at})

    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    server = create_server(
        build_search(settings),
        host=os.environ.get("JOURNEY_SEARCH_HOST", "127.0.0.1"),
        port=int(os.environ.get("JOURNEY_SEARCH_PORT", "8000")),
        log_queries=os.environ.get("JOURNEY_SEARCH_LOG_QUERIES", "").lower() == "true",
    )
    log_event(event="start", table=settings.table_name, index=settings.vector_index_name)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
