"""Wire DTOs for the durable_poc API.

These describe the JSON shapes crossing the HTTP boundary. Internally the
app still works with the loosely-typed dicts `agent.tools` already returns
(`_to_dict`-flattened Temporal query results) — these models only constrain
what routes accept and document what they return.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StartRunRequest(BaseModel):
    """Request to start a new workflow run."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)


class StartRunResponse(BaseModel):
    """The Temporal execution ID created for a new run."""

    workflow_id: str


class InputSubmissionRequest(BaseModel):
    """A value submitted for the field a run is currently awaiting."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    value: Any = None


class RunStateDTO(BaseModel):
    """Current state of one workflow run, as returned by `tools.get_workflow_state`."""

    model_config = ConfigDict(extra="allow")

    workflow_id: str
    status: str
    awaiting: dict[str, Any] | None = None
    transcript: list[dict[str, Any]] = Field(default_factory=list)


class ActiveWorkflowDTO(BaseModel):
    """One entry in the list of currently-running Temporal executions."""

    id: str
    status: str


class AutonomyPolicy(BaseModel):
    """Sliders/toggles governing the `/agentic` autonomous answerer.

    Kept to 2-3 controls, not a general policy DSL — see the plan's Section 3.
    """

    model_config = ConfigDict(extra="forbid")

    autonomy_level: Literal["cautious", "balanced", "assertive"] = "balanced"
    notify_categories: list[str] = Field(
        default_factory=lambda: ["identity", "payment", "irreversible"]
    )
    pause_before_external_call: bool = True


class SetAutonomyRequest(BaseModel):
    """`POST /runs/{id}/autonomy` body: the policy plus the profile bundle the
    autonomous answerer should treat as ground truth for this run."""

    model_config = ConfigDict(extra="forbid")

    policy: AutonomyPolicy = Field(default_factory=AutonomyPolicy)
    profile_fixture: str = Field(
        min_length=1,
        description=(
            "Path under durable_poc/evaluation/scenarios whose conversation.json "
            "supplies the seeded profile, e.g. "
            "'maternity_allowance/claim_start_date_today'."
        ),
    )
