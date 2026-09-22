"""Answer proposal logic using the existing WorkflowAgent.

The agent examines the current awaiting input, its SFSM schema,
and the conversation history to decide whether it already has enough
information to propose a typed answer.

The proposal is a structured response — NOT a request for the agent
to choose the next journey state.

Policy enforcement happens OUTSIDE the LLM: the application prevents
submissions that the selected policy does not permit.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

PROPOSAL_PROMPT_TEMPLATE = """\
You are examining a form question to decide if you already know the answer \
from the conversation so far.

Current question:
  Prompt: {prompt}
  Schema: {schema}

Your task:
1. Based ONLY on what the user has already told you in this conversation, \
do you have enough information to answer this question?
2. If yes, provide the exact typed value that should be submitted. \
The value MUST match the schema:
   - For "boolean": true or false
   - For "select_one": the exact option value string from the options list
   - For "select_many": a JSON array of option value strings
   - For "string": a plain string
3. If you are not confident, say you don't know.

Respond with ONLY a JSON object (no markdown fencing):
{{
  "has_answer": true/false,
  "value": <the typed value or null>,
  "explanation": "brief reason"
}}
"""


async def propose_answer(
    *,
    agent: Any,
    awaiting: dict[str, Any],
    session_state: dict[str, Any],
) -> dict[str, Any]:
    """Ask the agent to propose a typed answer for the current question.

    Args:
        agent: A WorkflowAgent instance with existing conversation history.
        awaiting: The current AwaitingInput dict from Temporal.
        session_state: The full session state dict for context.

    Returns:
        A dict with keys: has_answer (bool), value (Any|None), explanation (str).
    """
    prompt_text = awaiting.get("prompt", "")
    schema = awaiting.get("schema", {})

    proposal_prompt = PROPOSAL_PROMPT_TEMPLATE.format(
        prompt=prompt_text,
        schema=json.dumps(schema, indent=2),
    )

    try:
        response = await agent.respond(proposal_prompt, context=session_state)
        return _parse_proposal_response(response, schema)
    except Exception:
        logger.exception("Failed to get answer proposal from agent")
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
