"""Tests for the Gradio chat interface."""

from __future__ import annotations

from typing import Any

import pytest

from agent.chat import create_app, create_chat_fn


class FakeAgent:
    """Agent that records calls and returns a canned response."""

    def __init__(
        self,
        response: str = "I can help with that.",
        session_state: dict[str, Any] | None = None,
    ) -> None:
        self.response = response
        self.session_state = session_state
        self.calls: list[dict[str, Any]] = []

    async def respond(self, message: str, *, context: dict[str, Any] | None = None) -> str:
        self.calls.append({"message": message, "context": context})
        return self.response


@pytest.mark.asyncio
async def test_chat_fn_delegates_message_to_agent() -> None:
    """The chat function passes the user message to the agent and returns its response."""
    agent = FakeAgent(response="Let me start that workflow for you.")
    chat_fn = create_chat_fn(agent)

    result, state = await chat_fn("I need to change my address", [], None)

    assert result == "Let me start that workflow for you."
    assert agent.calls[0]["message"] == "I need to change my address"


@pytest.mark.asyncio
async def test_chat_fn_passes_state_as_context() -> None:
    """When session state exists, it is passed to the agent as context."""
    session_state = {
        "workflow_id": "sfsm-dvla.change_of_address-0.2.0",
        "awaiting": {
            "token": "tkn_2",
            "prompt": "Enter your postcode.",
            "schema": {"kind": "string"},
        },
    }
    agent = FakeAgent(session_state=session_state)
    chat_fn = create_chat_fn(agent)

    result, new_state = await chat_fn("SW1A 2AA", [], None)

    assert agent.calls[0]["context"] == session_state


@pytest.mark.asyncio
async def test_chat_fn_returns_updated_state_from_agent() -> None:
    """The chat function returns the agent's session_state after respond()."""
    agent = FakeAgent(
        session_state={
            "workflow_id": "sfsm-dvla.change_of_address-0.2.0",
            "awaiting": {"token": "tkn_1", "prompt": "Confirm?", "schema": {"kind": "boolean"}},
        }
    )
    chat_fn = create_chat_fn(agent)

    _result, state = await chat_fn("I need to change my address", [], None)

    assert state is not None
    assert state["workflow_id"] == "sfsm-dvla.change_of_address-0.2.0"


def test_create_app_returns_gradio_interface() -> None:
    """The app factory returns a launchable Gradio Blocks instance."""
    agent = FakeAgent()
    app = create_app(agent)

    assert app is not None
    assert hasattr(app, "launch")
