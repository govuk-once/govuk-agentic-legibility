"""Strands tool exposing service journey search to the orchestrating agent.

The tool is stateless: each call is one hybrid search over the catalogue. It
returns candidates only; deciding relevance, asking the user to clarify and
starting a journey are all the orchestrator's job.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, cast

from strands import tool

from forms_search.search import METHODS, JourneySearch, Method

logger = logging.getLogger(__name__)

# Retrieval method behind the tool; switch with $FORMS_SEARCH_METHOD to compare
# orchestrator behaviour with embedding-only or BM25 results.
SEARCH_METHOD = cast(Method, os.environ.get("FORMS_SEARCH_METHOD", "hybrid"))
if SEARCH_METHOD not in METHODS:
    raise ValueError(f"FORMS_SEARCH_METHOD must be one of {METHODS}")

DEFAULT_LIMIT = 5
MAX_LIMIT = 20

_index: JourneySearch | None = None


def get_index() -> JourneySearch:
    global _index
    if _index is None:
        _index = JourneySearch.from_environment()
    return _index


def set_index(index: JourneySearch | None) -> None:
    """Swap the index (for tests, or to compare catalogues/models)."""
    global _index
    _index = index


def search_payload(
    query: str, limit: int = DEFAULT_LIMIT, index: JourneySearch | None = None
) -> dict[str, Any]:
    """The JSON the orchestrator sees. Kept separate so its size can be inspected."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    hits = (index or get_index()).search(query, limit, SEARCH_METHOD)
    # Exactly the response shape in the Journey Search Contract RFC.
    return {
        "candidates": [
            {
                "workflow_id": hit.journey.workflow_id,
                "title": hit.journey.title,
                "description": hit.journey.description,
            }
            for hit in hits
        ],
    }


def payload_size(payload: dict[str, Any]) -> dict[str, int]:
    """Rough size of a tool result as the model receives it (compact JSON)."""
    chars = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return {"chars": chars, "approx_tokens": round(chars / 4)}


@tool
def search_service_journeys(query: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Search the catalogue of UK government service journeys and return a ranked shortlist of candidates.

    A service journey is an online government form the user can complete,
    such as applying, registering, reporting, claiming, requesting,
    notifying, amending, booking, complaining or giving feedback. The
    catalogue has about 550 journeys across many departments, agencies and
    public bodies. Many are niche or surprising, for example reporting an
    octopus sighting, applying to hold a maypole dance or registering a
    fishing vessel. Do not assume a service does not exist: if the user
    might want to do something that a government form could handle, search
    for it.

    Write the query in plain words describing what the user wants to do and
    what it is about, for example "report a dangerous goods spill on a road"
    or "change my redundancy claim for unpaid holiday". The user does not
    need to know the service's name. Do not put the user's personal details
    in the query.

    Results are candidates, not confirmed matches. They are ranked
    approximately and some may be irrelevant. Compare each title and
    description with what the user asked for. If several fit, ask the user
    which applies. If none fits, try different wording, ask for more detail,
    or tell the user that no suitable service was found. Searching does not
    start a journey or contact anyone.

    This tool is not for answering general information questions, such as
    what the travel advice for a country is. It is only for finding a form
    the user can complete.

    Args:
        query: Plain-language description of what the user wants to do.
        limit: How many candidates to return (default 5, maximum 20). Use a
            higher number when the request is vague or broad, or when an
            earlier search found nothing suitable.
    """
    try:
        payload = search_payload(query, limit)
    except Exception:
        logger.exception("search_service_journeys failed for query %r", query)
        raise
    logger.info(
        "search_service_journeys %r -> %d candidates (%d chars)",
        query,
        len(payload["candidates"]),
        payload_size(payload)["chars"],
    )
    return {"status": "success", "content": [{"json": payload}]}
