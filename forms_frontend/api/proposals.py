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
from typing import Any, TYPE_CHECKING

from forms_frontend.api.tracing import session_span, fields, error

if TYPE_CHECKING:
    from forms_frontend.api.sessions import FormSession

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
    session: FormSession | None = None,
) -> dict[str, Any]:
    """Trace the tool-less proposal agent without changing its submission authority.

    A fresh Strands agent is created on each call. Its input, messages, raw
    output and post-parse value are all kept for evaluation. Model-internal
    reasoning and any provider-hidden request fields are not available here.
    """
    prompt_text = awaiting.get("prompt", "")
    schema = awaiting.get("schema") or {}
    presentation = schema.get("presentation") or {}
    user_prompt = PROPOSAL_USER_TEMPLATE.format(
        prompt=prompt_text, schema=json.dumps(schema, indent=2),
    )
    strands_messages = _to_strands_messages(conversation_history)
    with session_span(
        "forms.proposal.invoke", session,
        current_question=awaiting, state_id=awaiting.get("state_id"),
        process_id=awaiting.get("process_id"), token=awaiting.get("token"),
        schema=schema, options=awaiting.get("options") or schema.get("options"),
        conversation=conversation_history, strands_messages=strands_messages,
        system_prompt=PROPOSAL_SYSTEM_PROMPT, user_prompt=user_prompt,
        model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6"),
    ) as span:
        if presentation.get("repeat_control") is True:
            result = {"has_answer": False, "value": None,
                      "explanation": "Confirm whether another repeated answer is needed."}
            fields(span, outcome="skipped_repeat_control", proposal=result)
            return result
        if schema.get("kind") == "file_ref":
            result = {"has_answer": False, "value": None,
                      "explanation": "Upload the file, or skip this optional question."}
            fields(span, outcome="skipped_file_ref", proposal=result)
            return result

        try:
            model = _get_model()
            proposal_agent = Agent(
                model=model, system_prompt=PROPOSAL_SYSTEM_PROMPT,
                tools=[], messages=strands_messages,
            )
            # Parent context stays active across the async Strands invocation.
            # Do not enable duplicate instrumentation on the shared WorkflowAgent.
            result = await proposal_agent.invoke_async(user_prompt)
            response = str(result)
            fields(span, model_response=response,
                   strands_messages_after=proposal_agent.messages)
            parsed = _parse_proposal_response(response, schema)
            fields(span, parsed_proposal=parsed, normalised_value=parsed.get("value"),
                   usable=bool(parsed.get("has_answer") and parsed.get("value") is not None),
                   schema_valid=_trace_schema_valid(parsed, schema),
                   outcome="proposed" if parsed.get("has_answer") else "no_answer")
            return parsed
        except Exception as exc:
            error(span, exc)
            logger.exception("Failed to get answer proposal from LLM")
            fallback = {"has_answer": False, "value": None,
                        "explanation": "Agent unavailable"}
            fields(span, outcome="error", proposal=fallback)
            return fallback


def _trace_schema_valid(proposal: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Observation only: do not change the existing proposal/submission policy."""
    if not proposal.get("has_answer") or proposal.get("value") is None:
        return False
    value = proposal["value"]
    kind = schema.get("kind")
    if kind == "boolean":
        return type(value) is bool
    if kind in ("select_one", "select_many"):
        options = schema.get("options") or []
        allowed = [o.get("value") if isinstance(o, dict) else o for o in options]
        if kind == "select_one":
            return value in allowed
        return isinstance(value, list) and all(v in allowed for v in value)
    if kind == "string":
        return isinstance(value, str)
    return True


def _parse_proposal_response(
    response: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """Parse the agent's JSON proposal response."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")] # noqa: E741
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
