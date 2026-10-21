"""Pydantic models for the FSM schema."""

from typing import Any, Literal, Callable, Annotated

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Registry
# ============================================================================


class OperationSpec(BaseModel):
    """Metadata and callable for a single registered operation."""

    name: str
    fn: Callable[[dict, dict], Any]
    description: str
    spec_schema: dict[str, Any]
    example: dict[str, Any] | None = None


class InvalidSpecNameException(Exception):
    """Raised when an operation name is not found or already registered."""


class OperationsRegistry:
    """Registry of named operations available to the AssignState handler.

    Operations are registered at import time via the ``@operation`` decorator
    in ``src/actions.py`` and looked up by name during workflow execution.
    """

    def __init__(self):
        self.registry: list[OperationSpec] = []

    def register(self, op_spec: OperationSpec):
        """Add an operation to the registry.

        Args:
            op_spec: The operation specification to register.

        Raises:
            InvalidSpecNameException: If an operation with the same name
                is already registered.
        """
        existing_names = [spec for spec in self.registry if spec.name == op_spec.name]
        if len(existing_names) > 0:
            raise InvalidSpecNameException("A spec with this name already exists in the registry")
        else:
            self.registry.append(op_spec)

    def execute(self, name: str, spec: dict, context: dict) -> Any:
        """Look up an operation by name and invoke it."""
        op_spec = self.get_op(name)
        return op_spec.fn(spec, context)

    def list_ops(self) -> list[OperationSpec]:
        """Return all registered operation specs."""
        return self.registry

    def get_op(self, name: str) -> OperationSpec:
        """Return a single operation spec by name."""
        try:
            return [op for op in self.registry if op.name == name][0]
        except IndexError:
            raise InvalidSpecNameException(f"There is no operation spec with the name {name}")


# ============================================================================
# Type aliases
# ============================================================================


SchemaKind = Literal[
    "boolean",
    "string",
    "select_one",
    "select_many",
    "file_ref",
]

Channel = Literal[
    "transcript",
    "email",
    "sms",
]

HttpMethod = Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
]

CompletionStatus = Literal[
    "success",
    "cancelled",
    "failed",
    "offramp",
    "needs_attention",
]

WorkflowState = Literal[
    "draft",
    "live",
    "deprecated",
    "retired",
]


# ============================================================================
# Supporting Models
# ============================================================================


class OptionItem(BaseModel):
    """A selectable option with a machine value and human-readable label."""

    value: str
    label: str


class DynamicRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(alias="$")


class FieldDefinition(BaseModel):
    name: str
    label: str | None = None
    schema_: "SchemaDefinition" = Field(
        alias="schema"
    )


class TimeoutConfig(BaseModel):
    after: str | dict[str, str]
    next: str


class Timeouts(BaseModel):
    start_to_close: str | None = None
    schedule_to_close: str | None = None
    heartbeat: str | None = None


class RetryPolicy(BaseModel):
    max_attempts: int
    initial_interval: str | None = None
    backoff_coefficient: float | None = None
    max_interval: str | None = None
    retry_on: list[str] = Field(default_factory=list)


class ActivityDefaults(BaseModel):
    timeouts: Timeouts | None = None
    retry: RetryPolicy | None = None


class CatchClause(BaseModel):
    """Defines behaviour for given events or exceptions."""
    on: str
    next: str


class CaptureSpec(BaseModel):
    from_: str = Field(alias="from")
    pick: list[str] | None = None
    max_items: int | None = None
    max_length: int | None = None


class Condition(BaseModel):
    op: str
    path: str | None = None
    value: Any | None = None
    value_path: str | None = None
    all: list["Condition"] | None = None
    any: list["Condition"] | None = None


class ChoiceRule(BaseModel):
    """A single predicate-guarded transition in a ChoiceState."""
    when: Condition
    next: str


class Metadata(BaseModel):
    """Extensible metadata attached to workflows, processes and states."""
    model_config = ConfigDict(extra="allow")


# ============================================================================
# Schema Definition
# ============================================================================


class SchemaDefinition(BaseModel):
    """Schema describing the expected shape and constraints of an InputState value.

    The ``kind`` field determines validation behaviour (e.g. ``"string"``,
    ``"boolean"``, ``"select_one"``).  Optional fields such as ``pattern``,
    ``options``, and ``normalise`` refine the validation and presentation.
    """

    model_config = ConfigDict(extra="allow")
    kind: SchemaKind
    pattern: str | None = None
    normalise: str | None = None
    max_length: int | None = None
    invalid_message: str | None = None
    fields: list[FieldDefinition] | None = None
    options: list[OptionItem] | None = None
    options_from: str | None = None
    value_key: str | None = None
    label_key: str | None = None
    default: Any | None = None
    accept: list[str] | None = None
    allow_skip: bool | None = False
    max_bytes: int | None = None
    declared_only: bool | None = None


# ============================================================================
# States
# ============================================================================


class BaseState(BaseModel):
    """Abstract base for all FSM state types."""
    type: str
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputState(BaseState):
    """Suspends execution and awaits structured human input.

    Exposes a prompt, an input schema, and optional timeout/retry
    configuration.  The received value is written to the variable
    named by ``assign``.
    """

    type: Literal["input"] = "input"
    prompt: str
    schema_: SchemaDefinition = Field(alias="schema")
    assign: str
    on_invalid: str | None = None
    timeout: TimeoutConfig | None = None
    next: str


class OutputState(BaseState):
    """Emits a transcript entry or dispatches an external notification.

    When ``channel`` is ``"transcript"`` the message is appended to the
    audit log.  Other channels trigger a ``notify`` activity for
    external delivery (email, SMS, etc.).
    """

    type: Literal["output"] = "output"
    channel: Channel
    message: str | None = None
    template: str | None = None
    params: dict[str, Any] | None = None
    idempotency_key: str | None = None
    also_transcript: str | None = None
    on_error: Literal["continue", "fail"] = "fail"
    next: str


class CallState(BaseState):
    """Dispatches an HTTP API request via a Temporal activity.

    The response is projected through ``capture`` rules and assigned
    into the frame variable named by ``assign``.  Error routes are
    defined in ``catch``.
    """

    type: Literal["call"] = "call"
    method: HttpMethod
    url: str
    service: str
    headers: dict[str, str] | None = None
    body: dict[str, Any] | None = None
    source_ref: dict[str, Any] | None = None
    encoding: str | None = None
    idempotency_key: str | None = None
    timeouts: Timeouts | None = None
    retry: RetryPolicy | None = None
    assign: str
    capture: dict[str, str | CaptureSpec] | None = None
    catch: list[CatchClause] | None = None
    next: str


class ChoiceState(BaseState):
    """Presents one of more choices in a workflow."""
    type: Literal["choice"] = "choice"
    rules: list[ChoiceRule]
    default: str


class AssignState(BaseState):
    """Populates or calculates required values within a workflow."""
    type: Literal["assign"] = "assign"
    set: dict[str, Any]

    next: str


class InvokeState(BaseState):
    """Calls a sub-process."""
    type: Literal["invoke"] = "invoke"
    process: str
    assign: str | None = None
    input: dict[str, Any] | None = None
    catch: list[CatchClause] | None = None
    next: str


class WaitState(BaseState):
    """Causes the workflow to pause for a specified duration."""
    type: Literal["wait"] = "wait"
    duration: str | dict[str, str]
    next: str


class EndState(BaseState):
    """Ends a workflow or sub-process. Optional value returned to the invoking process.

    May be a scalar, object, list, or dynamically resolved reference.
    """
    type: Literal["end"] = "end"
    status: CompletionStatus
    outcome: str | None = None
    return_: Any | None = Field(
        default=None,
        alias="return",
    )


State = Annotated[
    (
        InputState
        | OutputState
        | CallState
        | ChoiceState
        | AssignState
        | InvokeState
        | WaitState
        | EndState
    ),
    Field(discriminator="type"),
]


# ============================================================================
# Processes
# ============================================================================


class Process(BaseModel):
    start: str
    vars: dict[str, Any] = Field(default_factory=dict)
    states: dict[str, State]
    performer: str | None = None
    parent_process: str | None = None
    source: list[str] = Field(default_factory=list)
    window: dict[str, str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Workflow
# ============================================================================


class WorkflowExecutorConfig(BaseModel):
    workflow_id_template: str | None = None
    id_reuse_policy: str | None = None
    run_timeout: str | None = None
    continue_as_new: dict[str, Any] | None = None
    search_attributes: dict[str, Any] | None = None


class SFSMDefinition(BaseModel):
    schema_: str = Field(alias="schema")
    workflow_id: int | str | None = None
    id: str
    version: str
    entry: str
    executor: WorkflowExecutorConfig
    defaults: dict[str, ActivityDefaults] = Field(default_factory=dict)
    processes: dict[str, Process]
    owner: str | None = None
    contact: str | None = None
    description: str | None = None
    state: WorkflowState = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)
