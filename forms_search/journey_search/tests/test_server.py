"""Tests for the MCP contract, through a real MCP client session in memory."""

from __future__ import annotations

import pytest
from conftest import FakeEmbedder, FakeStore
from mcp.shared.memory import create_connected_server_and_client_session
from starlette.testclient import TestClient

from journey_search.contract import DEFAULT_LIMIT, TOOL_NAME
from journey_search.search import JourneySearch
from journey_search.server import create_server

pytestmark = pytest.mark.anyio


def make_server(store: FakeStore | None = None):
    return create_server(JourneySearch(FakeEmbedder(), store or FakeStore()))


async def test_server_exposes_exactly_one_tool_with_the_contract_schema():
    async with create_connected_server_and_client_session(make_server()) as client:
        tools = (await client.list_tools()).tools

    assert [t.name for t in tools] == [TOOL_NAME]
    tool = tools[0]
    assert "Results are candidates, not confirmed matches" in tool.description
    assert tool.inputSchema["required"] == ["query"]
    assert tool.inputSchema["properties"]["limit"]["default"] == DEFAULT_LIMIT
    assert set(tool.outputSchema["properties"]) == {"candidates"}
    assert tool.annotations.readOnlyHint is True


async def test_tool_call_returns_ranked_candidates():
    async with create_connected_server_and_client_session(make_server()) as client:
        result = await client.call_tool(TOOL_NAME, {"query": "report a mosquito", "limit": 2})

    assert not result.isError
    candidates = result.structuredContent["candidates"]
    assert [c["workflow_id"] for c in candidates] == ["3652", "265276"]
    assert set(candidates[0]) == {"workflow_id", "title", "description"}


async def test_limit_defaults_to_five():
    store = FakeStore()
    async with create_connected_server_and_client_session(make_server(store)) as client:
        await client.call_tool(TOOL_NAME, {"query": "claim"})
    assert store.calls[0][1] == DEFAULT_LIMIT


async def test_empty_query_is_a_tool_error_not_a_crash():
    async with create_connected_server_and_client_session(make_server()) as client:
        result = await client.call_tool(TOOL_NAME, {"query": "   "})
    assert result.isError
    assert "query must not be empty" in result.content[0].text


async def test_dependency_failures_do_not_leak_internal_details():
    store = FakeStore(error=RuntimeError("arn:aws:dynamodb:eu-west-2:123:table/secret-name"))
    async with create_connected_server_and_client_session(make_server(store)) as client:
        result = await client.call_tool(TOOL_NAME, {"query": "mosquito"})
    assert result.isError
    assert "temporarily unavailable" in result.content[0].text
    assert "arn:aws" not in result.content[0].text


def test_ping_reports_healthy_with_a_stable_timestamp():
    with TestClient(make_server().streamable_http_app()) as http:
        first, second = http.get("/ping").json(), http.get("/ping").json()
    assert first["status"] == "Healthy"
    assert first["time_of_last_update"] == second["time_of_last_update"]
