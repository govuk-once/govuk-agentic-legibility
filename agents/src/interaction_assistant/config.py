"""Environment configuration for the interaction assistant."""

from __future__ import annotations

import os

from agents.src.interaction_assistant.assistant import InteractionAssistant

DEFAULT_AGENT_REGION = "eu-west-2"


def create_environment_assistant() -> InteractionAssistant | None:
    """Create the configured Strands assistant, or return ``None`` when disabled.

    Returns:
        A configured assistant when `JOURNEY_AGENT_MODEL_ID` is set, otherwise
        ``None``.
    """
    model_id = os.environ.get("JOURNEY_AGENT_MODEL_ID")
    if not model_id:
        return None

    from agents.src.interaction_assistant.strands_assistant import (
        StrandsInteractionAssistant,
    )

    region_name = (
        os.environ.get("JOURNEY_AGENT_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_AGENT_REGION
    )
    return StrandsInteractionAssistant(
        model_id=model_id,
        region_name=region_name,
    )
