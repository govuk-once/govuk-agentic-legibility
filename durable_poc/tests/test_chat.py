"""Tests for the Gradio chat interface."""

from __future__ import annotations

from agent.chat import create_app, create_chat_fn


class FakeAgent:
    """Agent that records calls and returns a canned response."""

    def __init__(self, response: str = "I can help with that.") -> None:
        self.response = response
        self.calls: list[str] = []

    def respond(self, message: str) -> str:
        self.calls.append(message)
        return self.response


def test_chat_fn_delegates_message_to_agent() -> None:
    """The chat function passes the user message to the agent and returns its response."""
    agent = FakeAgent(response="Let me start that workflow for you.")
    chat_fn = create_chat_fn(agent)

    result = chat_fn("I need to change my address", [])

    assert result == "Let me start that workflow for you."
    assert agent.calls == ["I need to change my address"]


def test_chat_fn_accepts_history_parameter() -> None:
    """The chat function accepts conversation history without error."""
    agent = FakeAgent()
    chat_fn = create_chat_fn(agent)

    history: list[dict[str, str]] = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    result = chat_fn("What can you help with?", history)

    assert isinstance(result, str)
    assert agent.calls == ["What can you help with?"]


def test_create_app_returns_gradio_interface() -> None:
    """The app factory returns a launchable Gradio Blocks instance."""
    agent = FakeAgent()
    app = create_app(agent)

    assert app is not None
    assert hasattr(app, "launch")
