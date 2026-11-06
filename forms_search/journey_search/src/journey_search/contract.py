"""The tool contract the orchestrator sees, as agreed in the Journey Search Contract RFC.

Nothing here depends on how candidates are retrieved, so the retrieval
implementation can change without changing the contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

TOOL_NAME = "search_service_journeys"
DEFAULT_LIMIT = 5
MAX_LIMIT = 20
MAX_QUERY_CHARS = 1000

TOOL_DESCRIPTION = """\
Search the catalogue of UK government service journeys and return a ranked shortlist of candidates.

A service journey is an online government form the citizen can complete, such as applying, \
registering, reporting, claiming, requesting, notifying, amending, booking, complaining or giving \
feedback. The catalogue has about 550 journeys across many departments, agencies and public bodies. \
Many are niche or surprising, for example reporting an octopus sighting or registering a fishing \
vessel. Do not assume a service does not exist: if the citizen might want to do something that a \
government form could handle, search for it.

Write the query in plain words describing what the citizen wants to do and what it is about, for \
example "report a dangerous goods spill on a road" or "change my redundancy claim for unpaid \
holiday". The citizen does not need to know the service's name. Do not put the citizen's personal \
details in the query.

Results are candidates, not confirmed matches. They are ranked approximately and some may be \
irrelevant. You must judge whether each candidate is suitable, even when only one is returned. If \
several fit, ask the citizen which applies. If none fits, try different wording, ask for more \
detail, or use another capability. Searching does not start a journey, contact anyone or keep any \
state between calls.

This tool is not for answering general information questions, such as what the travel advice for \
a country is. It is only for finding a form the citizen can complete."""

QUERY_DESCRIPTION = "Plain-language description of what the citizen wants to do."
LIMIT_DESCRIPTION = (
    f"Maximum number of candidates to return (default {DEFAULT_LIMIT}, maximum {MAX_LIMIT}; "
    f"larger values are reduced to {MAX_LIMIT}). Use a higher number when the request is vague "
    "or an earlier search found nothing suitable."
)


class Candidate(BaseModel):
    workflow_id: str = Field(description="Identifier used to start the journey elsewhere.")
    title: str = Field(description="The journey's title.")
    description: str = Field(description="A brief description of what the journey is for.")


class SearchResponse(BaseModel):
    """Ranked candidates, most likely first. Candidates are not confirmed matches."""

    candidates: list[Candidate]


def clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def normalise_query(query: str) -> str:
    """Collapse whitespace and check the query is usable; raises ValueError otherwise."""
    query = " ".join(query.split())
    if not query:
        raise ValueError("query must not be empty")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must be at most {MAX_QUERY_CHARS} characters")
    return query
