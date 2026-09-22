"""Answer proposal logic using a tool-less LLM call.

The proposal agent examines the current awaiting input, its SFSM schema,
and the conversation history to decide whether it already has enough
information to propose a typed answer.

IMPORTANT: This uses a separate Agent instance WITHOUT workflow tools.
The proposal agent can only respond with text — it cannot submit answers,
query workflows, or take any actions. Policy enforcement (whether to
actually submit the proposed value) happens in the application layer.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

from strands import Agent
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

PROPOSAL_SYSTEM_PROMPT = """\
You are a form-filling assistant. You have had a conversation with a user \
and now you are examining form questions one at a time to decide whether \
you already know the answer from what the user told you.

You must respond with ONLY a JSON object. No markdown fencing, no \
explanation outside the JSON. The JSON must have exactly these keys:
{
  "has_answer": true or false,
  "value": the typed value or null,
  "explanation": "brief reason"
}

Rules:
- Only propose an answer if the user clearly stated the information.
- Do NOT guess, infer, or fabricate answers.
- The value MUST match the schema type exactly:
  - "boolean": use true or false (not strings)
  - "select_one": use the exact option value from the options list
  - "select_many": use a JSON array of exact option values
  - "string": use a plain string
- If the schema has options, you MUST use one of the listed option values.
- If you are not confident, set has_answer to false.
"""

PROPOSAL_USER_TEMPLATE = """\
Current form question:
  Prompt: {prompt}
  Schema: {schema}

Based ONLY on our conversation so far, do you know the answer to this question?
Respond with ONLY the JSON object."""


def _to_strands_messages(conversation: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Convert simple {role, content} messages to Strands format and deep-copy."""
    if not conversation:
        return []
    messages = []
    for msg in conversation:
        content = msg.get("content", "")
        if isinstance(content, str):
            content = [{"text": content}]
        else:
            content = copy.deepcopy(content)
        messages.append({"role": msg["role"], "content": content})
    return messages


def _get_model() -> BedrockModel:
    return BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
        temperature=0.0,
    )


async def propose_answer(
    *,
    conversation_history: list[dict[str, Any]],
    awaiting: dict[str, Any],
) -> dict[str, Any]:
    """Ask a tool-less LLM to propose a typed answer for the current question.

    Uses a separate Agent instance with NO tools — it can only respond with
    text, never submit answers or query workflows.

    Args:
        conversation_history: The conversation so far (user/assistant messages).
        awaiting: The current AwaitingInput dict from Temporal.

    Returns:
        A dict with keys: has_answer (bool), value (Any|None), explanation (str).
    """
    prompt_text = awaiting.get("prompt", "")
    schema = awaiting.get("schema", {})

    user_prompt = PROPOSAL_USER_TEMPLATE.format(
        prompt=prompt_text,
        schema=json.dumps(schema, indent=2),
    )

    try:
        model = _get_model()
        strands_messages = _to_strands_messages(conversation_history)
        proposal_agent = Agent(
            model=model,
            system_prompt=PROPOSAL_SYSTEM_PROMPT,
            tools=[],
            messages=strands_messages,
        )
        result = await proposal_agent.invoke_async(user_prompt)
        response = str(result)
        logger.info("Proposal response for %r: %s", prompt_text[:50], response[:200])
        return _parse_proposal_response(response, schema)
    except Exception:
        logger.exception("Failed to get answer proposal from LLM")
        return {"has_answer": False, "value": None, "explanation": "Agent unavailable"}


def _parse_proposal_response(
    response: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """Parse the agent's JSON proposal response."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("Could not parse proposal response: %s", text[:200])
                return {
                    "has_answer": False,
                    "value": None,
                    "explanation": "Could not parse agent response",
                }
        else:
            return {
                "has_answer": False,
                "value": None,
                "explanation": "Could not parse agent response",
            }

    has_answer = bool(parsed.get("has_answer", False))
    value = parsed.get("value")
    explanation = str(parsed.get("explanation", ""))

    if has_answer and value is not None:
        value = _coerce_proposal_value(value, schema)

    return {"has_answer": has_answer, "value": value, "explanation": explanation}


def _coerce_proposal_value(value: Any, schema: dict[str, Any]) -> Any:
    """Coerce the proposed value to match the SFSM schema kind."""
    kind = schema.get("kind")

    if kind == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "yes", "y", "1")

    if kind == "string":
        return str(value)

    if kind == "select_one":
        options = schema.get("options", [])
        str_value = str(value).strip()
        for opt in options:
            if isinstance(opt, dict):
                if str_value.lower() in (
                    str(opt.get("value", "")).lower(),
                    str(opt.get("label", "")).lower(),
                ):
                    return opt.get("value", str_value)
        return str_value

    if kind == "select_many":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value]

    return value
