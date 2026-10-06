
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------
# Metadata
# ---------------------------------------

class WorkflowMetadata(BaseModel):
    name: str
    version: str = "1.0"


class ContractField(BaseModel):
    name: str
    type: str | None = None
    required: bool = False


class ProcessContract(BaseModel):
    inputs: list[ContractField] = Field(default_factory=list)
    outputs: list[ContractField] = Field(default_factory=list)


# ---------------------------------------
# Forms
# ---------------------------------------

class FileConstraints(BaseModel):
    max_size: int | None = None
    allowed_types: str | None = None


class FormOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    id: str
    type: str

    variable: str | None = None
    source_variable: str | None = None

    label: str | None = None
    required: bool = False

    file_constraints: FileConstraints | None = None

    options: list[FormOption] = Field(
        default_factory=list,
    )


class FormDefinition(BaseModel):
    title: str | None = None

    fields: list[FormField] = Field(
        default_factory=list,
    )


# ---------------------------------------
# Mappings
# ---------------------------------------

class MappingItem(BaseModel):
    source: str
    target: str


class MappingDefinition(BaseModel):
    inputs: list[MappingItem] = Field(default_factory=list)
    outputs: list[MappingItem] = Field(default_factory=list)

# ---------------------------------------
# HTTP
# ---------------------------------------

class RetryPolicy(BaseModel):
    attempts: int = 1
    backoff_seconds: int = 0


class TimeoutPolicy(BaseModel):
    duration: str


class HttpServiceDefinition(BaseModel):
    service: str
    method: str
    endpoint: str

    inputs: list[MappingItem] = Field(
        default_factory=list,
    )

    outputs: list[MappingItem] = Field(
        default_factory=list,
    )

    retry: RetryPolicy | None = None
    timeout: TimeoutPolicy | None = None


# ---------------------------------------
# Messaging
# ---------------------------------------

class MessageDefinition(BaseModel):
    title: str | None = None
    text: str | None = None
    severity: str | None = None


class NotificationDefinition(BaseModel):
    channel: str

    outputs: list[MappingItem] = Field(
        default_factory=list,
    )


# ---------------------------------------
# Call Activity
# ---------------------------------------

class CallActivityMappings(BaseModel):
    inputs: list[MappingItem] = Field(
        default_factory=list,
    )

    outputs: list[MappingItem] = Field(
        default_factory=list,
    )

    validate_inputs: bool = False
    validate_outputs: bool = False


# ---------------------------------------
# BPMN Errors
# ---------------------------------------

class BPMNError(BaseModel):
    id: str
    name: str


# ---------------------------------------
# Sequence Flows
# ---------------------------------------

class SequenceFlow(BaseModel):
    id: str

    source_ref: str
    target_ref: str

    condition: str | None = None
    is_default: bool = False


# ---------------------------------------
# Base Node
# ---------------------------------------

class BPMNNode(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )

    id: str
    name: str | None = None
    type: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


# ---------------------------------------
# Events
# ---------------------------------------

class StartEvent(BPMNNode):
    type: Literal["startEvent"] = "startEvent"


class EndEvent(BPMNNode):
    type: Literal["endEvent"] = "endEvent"

    error_ref: str | None = None


class IntermediateCatchEvent(BPMNNode):
    type: Literal[
        "intermediateCatchEvent"
    ] = "intermediateCatchEvent"

    duration: str


class BoundaryEvent(BPMNNode):
    type: Literal["boundaryEvent"] = "boundaryEvent"

    attached_to_ref: str

    error_ref: str | None = None
    cancel_activity: bool = True


# ---------------------------------------
# Tasks
# ---------------------------------------

class UserTask(BPMNNode):
    type: Literal["userTask"] = "userTask"

    form: FormDefinition | None = None


class ServiceTask(BPMNNode):
    type: Literal["serviceTask"] = "serviceTask"

    http_service: HttpServiceDefinition | None = None


class ScriptTask(BPMNNode):
    type: Literal["scriptTask"] = "scriptTask"

    notification: NotificationDefinition | None = None
    mapping: MappingDefinition | None = None

    task_handler_type: Literal[
        "mapping",
        "notification",
        "validation",
    ] | None = None


class SendTask(BPMNNode):
    type: Literal["sendTask"] = "sendTask"
    message: MessageDefinition | None = None


class CallActivity(BPMNNode):
    type: Literal["callActivity"] = "callActivity"

    called_element: str

    mappings: CallActivityMappings = Field(
        default_factory=CallActivityMappings,
    )


# ---------------------------------------
# Gateways
# ---------------------------------------

class ExclusiveGateway(BPMNNode):
    type: Literal[
        "exclusiveGateway"
    ] = "exclusiveGateway"

    default_flow: str | None = None


# ---------------------------------------
# Node Union
# ---------------------------------------

Node = Annotated[
    (
        StartEvent
        | EndEvent
        | BoundaryEvent
        | IntermediateCatchEvent
        | UserTask
        | ServiceTask
        | ScriptTask
        | SendTask
        | CallActivity
        | ExclusiveGateway
    ),
    Field(discriminator="type"),
]


# ---------------------------------------
# Process
# ---------------------------------------

class BPMNProcess(BaseModel):
    id: str

    start_event: str

    workflow_metadata: WorkflowMetadata | None = None

    process_contract: ProcessContract | None = None

    variables: dict[str, Any] = Field(
        default_factory=dict,
    )

    nodes: dict[str, Node]
    flows: dict[str, SequenceFlow]

    def get_node(
        self,
        node_id: str,
    ) -> Node:

        return self.nodes[node_id]

    def outgoing_flows(
        self,
        node_id: str,
    ) -> list[SequenceFlow]:

        return [
            flow
            for flow in self.flows.values()
            if flow.source_ref == node_id
        ]

    def incoming_flows(
        self,
        node_id: str,
    ) -> list[SequenceFlow]:

        return [
            flow
            for flow in self.flows.values()
            if flow.target_ref == node_id
        ]

    def get_single_next_node_id(
        self,
        node_id: str,
    ) -> str:

        outgoing = self.outgoing_flows(
            node_id,
        )

        if len(outgoing) != 1:
            raise ValueError(
                f"Expected exactly one outgoing flow from '{node_id}', found {len(outgoing)}"
            )

        return outgoing[0].target_ref

    def boundary_target(
        self,
        task_id: str,
        error_ref: str,
    ) -> str | None:

        for node in self.nodes.values():

            if not isinstance(
                node,
                BoundaryEvent,
            ):
                continue

            if node.attached_to_ref != task_id:
                continue

            if node.error_ref != error_ref:
                continue

            outgoing = self.outgoing_flows(
                node.id,
            )

            if outgoing:
                return outgoing[0].target_ref

        return None


# ---------------------------------------
# Definition
# ---------------------------------------

class BPMNDefinition(BaseModel):
    schema_: str = Field(alias="schema")

    workflow_id: int | str | None = None

    id: str
    version: str
    entry: str

    errors: dict[str, BPMNError] = Field(
        default_factory=dict,
    )

    processes: dict[str, BPMNProcess]

    process_registry: dict[str, str] = Field(
    default_factory=dict,
)