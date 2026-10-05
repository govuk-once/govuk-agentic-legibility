"""
BPMN workflow definition models.

These models represent a compiled BPMN process that can be
executed by the Temporal BPMN interpreter.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


#
# Process Metadata
#


class WorkflowMetadata(BaseModel):
    """
    Metadata attached to a BPMN process.
    """

    name: str

    version: str = "1.0"


#
# Process Contracts
#


class ContractField(BaseModel):
    """
    Process input/output definition.
    """

    name: str

    type: str | None = None

    required: bool = False


class ProcessContract(BaseModel):
    """
    BPMN process contract.
    """

    inputs: list[ContractField] = Field(
        default_factory=list,
    )

    outputs: list[ContractField] = Field(
        default_factory=list,
    )


#
# Validation
#


class ValidationRule(BaseModel):
    expression: str

    message: str


class FieldValidation(BaseModel):
    pattern: str | None = None

    validator: str | None = None

    rule: str | None = None

    message: str | None = None


class FileConstraints(BaseModel):
    maxSize: int | None = None

    allowedTypes: str | None = None

    minWidth: int | None = None

    minHeight: int | None = None


#
# Forms
#

class FormOption(BaseModel):
    value: str
    label: str

class FormField(BaseModel):
    id: str
    variable: str
    type: str

    label: str | None = None

    required: bool = False

    validation: FieldValidation | None = None

    fileConstraints: FileConstraints | None = None

    source_variable: str | None = None

    options: list[FormOption] = Field(
        default_factory=list,
    )

class FormDefinition(BaseModel):
    title: str | None = None

    fields: list[FormField] = Field(
        default_factory=list,
    )


#
# Mappings
#


class MappingItem(BaseModel):
    source: str

    target: str


#
# HTTP Services
#


class RetryPolicy(BaseModel):
    attempts: int = 1

    backoffSeconds: int = 0


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


class NotificationDefinition(BaseModel):
    channel: str


#
# Call Activity
#

class MappingDefinition(BaseModel):
    inputs: list[MappingItem] = Field(
        default_factory=list,
    )

    outputs: list[MappingItem] = Field(
        default_factory=list,
    )

class CallActivityMappings(BaseModel):
    inputs: list[MappingItem] = Field(
        default_factory=list,
    )

    outputs: list[MappingItem] = Field(
        default_factory=list,
    )

    validate_inputs: bool = False

    validate_outputs: bool = False


#
# BPMN Errors
#


class BPMNError(BaseModel):
    id: str

    name: str


#
# Sequence Flows
#


class SequenceFlow(BaseModel):
    """
    Connection between BPMN nodes.

    Conditional flows are represented by
    BPMN conditionExpression text.
    """

    id: str

    source_ref: str

    target_ref: str

    condition: str | None = None

    is_default: bool = False


#
# Base Node
#


class BPMNNode(BaseModel):
    """
    Base BPMN node.
    """

    model_config = ConfigDict(
        extra="allow",
    )

    id: str

    name: str | None = None

    type: str

    #
    # Parsed BPMN extension elements.
    #
    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


#
# Events
#


class StartEvent(BPMNNode):
    type: Literal["startEvent"] = "startEvent"


class EndEvent(BPMNNode):
    type: Literal["endEvent"] = "endEvent"

    status: str = "completed"

    outcome: str | None = None

    error_ref: str | None = None


class TimerEvent(BPMNNode):
    type: Literal["timerEvent"] = "timerEvent"

    duration: str


class IntermediateCatchEvent(BPMNNode):
    type: Literal["intermediateCatchEvent"] = (
        "intermediateCatchEvent"
    )

    duration: str

class BoundaryEvent(BPMNNode):
    """
    Boundary event attached to a task.

    Example:

        <boundaryEvent
            attachedToRef="validate_photo">
    """

    type: Literal["boundaryEvent"] = "boundaryEvent"

    attached_to_ref: str

    error_ref: str | None = None

    cancel_activity: bool = True


#
# Tasks
#


class UserTask(BPMNNode):
    type: Literal["userTask"] = "userTask"

    form: FormDefinition | None = None


class ServiceTask(BPMNNode):
    type: Literal["serviceTask"] = "serviceTask"

    http_service: HttpServiceDefinition | None = None

class ScriptTask(BPMNNode):
    type: Literal["scriptTask"] = "scriptTask"

    task_handler_type: Literal[
        "validation",
        "mapping",
        "notification",
    ] | None = None

    validation_rules: list[ValidationRule] = Field(
        default_factory=list,
    )

    operations: dict[str, Any] = Field(
        default_factory=dict,
    )

    notification: NotificationDefinition | None = None

    mapping: MappingDefinition | None = None

class ManualTask(BPMNNode):
    type: Literal["manualTask"] = "manualTask"


class CallActivity(BPMNNode):
    type: Literal["callActivity"] = "callActivity"

    called_element: str

    mappings: CallActivityMappings = Field(
        default_factory=CallActivityMappings,
    )

#
# Gateways
#


class ExclusiveGateway(BPMNNode):
    type: Literal["exclusiveGateway"] = (
        "exclusiveGateway"
    )

    default_flow: str | None = None


class ParallelGateway(BPMNNode):
    type: Literal["parallelGateway"] = "parallelGateway"


#
# Node Union
#


Node = Annotated[
    (
        StartEvent
        | EndEvent
        | TimerEvent
        | BoundaryEvent
        | UserTask
        | ServiceTask
        | ScriptTask
        | ManualTask
        | CallActivity
        | ExclusiveGateway
        | ParallelGateway
        | IntermediateCatchEvent
    ),
    Field(discriminator="type"),
]


#
# BPMN Process
#


class BPMNProcess(BaseModel):
    """
    Executable BPMN process.
    """

    id: str

    start_event: str

    workflow_metadata: WorkflowMetadata | None = None

    process_contract: ProcessContract | None = None

    validation_rules: list[ValidationRule] = Field(
        default_factory=list,
    )

    variables: dict[str, Any] = Field(
        default_factory=dict,
    )

    nodes: dict[str, Node]

    flows: dict[str, SequenceFlow]

    #
    # Graph Helpers
    #

    def get_node(
        self,
        node_id: str,
    ) -> Node:
        """
        Return a node by id.
        """

        node = self.nodes.get(
            node_id,
        )

        if node is None:
            raise ValueError(f"Node '{node_id}' not found in process '{self.id}'")

        return node

    def start_node(
        self,
    ) -> Node:
        """
        Return the process start node.
        """

        return self.get_node(
            self.start_event,
        )

    def outgoing_flows(
        self,
        node_id: str,
    ) -> list[SequenceFlow]:
        """
        Return all outgoing sequence flows.
        """

        return [flow for flow in self.flows.values() if flow.source_ref == node_id]

    def incoming_flows(
        self,
        node_id: str,
    ) -> list[SequenceFlow]:
        """
        Return all incoming sequence flows.
        """

        return [flow for flow in self.flows.values() if flow.target_ref == node_id]

    def next_node_ids(
        self,
        node_id: str,
    ) -> list[str]:
        """
        Return ids of all reachable nodes.
        """

        return [
            flow.target_ref
            for flow in self.outgoing_flows(
                node_id,
            )
        ]

    def next_nodes(
        self,
        node_id: str,
    ) -> list[Node]:
        """
        Return all reachable BPMN nodes.
        """

        return [
            self.get_node(
                flow.target_ref,
            )
            for flow in self.outgoing_flows(
                node_id,
            )
        ]

    def get_single_next_node(
        self,
        node_id: str,
    ) -> Node:
        """
        Return the single outgoing node.

        Intended for:
        - StartEvent
        - UserTask
        - ServiceTask
        - TimerEvent
        - ManualTask
        """

        nodes = self.next_nodes(
            node_id,
        )

        if len(nodes) != 1:
            raise ValueError(
                f"Expected exactly one outgoing "
                f"path from '{node_id}', "
                f"found {len(nodes)}"
            )

        return nodes[0]

    def get_single_next_node_id(
        self,
        node_id: str,
    ) -> str:
        """
        Return the id of the single outgoing node.
        """

        return self.get_single_next_node(
            node_id,
        ).id

    def boundary_events_for(
        self,
        node_id: str,
    ) -> list[BoundaryEvent]:

        events = []

        for node in self.nodes.values():
            if isinstance(node, BoundaryEvent) and node.attached_to_ref == node_id:
                events.append(node)

        return events

    def boundary_target(
        self,
        node_id: str,
        error_ref: str,
    ) -> str | None:
        """
        Find boundary route for a specific BPMN error.
        """

        events = [
            e
            for e in self.boundary_events_for(
                node_id,
            )
            if e.error_ref == error_ref
        ]

        if not events:
            return None

        event = events[0]

        outgoing = self.outgoing_flows(
            event.id,
        )

        if not outgoing:
            return None

        return outgoing[0].target_ref


#
# Workflow Runtime Configuration
#


class WorkflowExecutorConfig(BaseModel):
    workflow_id_template: str | None = None

    id_reuse_policy: str | None = None

    run_timeout: str | None = None

    continue_as_new: dict[str, Any] | None = None

    search_attributes: dict[str, Any] | None = None


#
# BPMN Definition
#


class BPMNDefinition(BaseModel):
    """
    Top level BPMN workflow definition.

    Produced by the BPMN compiler.
    """

    schema_: str = Field(
        alias="schema",
    )

    workflow_id: int | str | None = None

    id: str

    version: str

    entry: str

    executor: WorkflowExecutorConfig = Field(
        default_factory=WorkflowExecutorConfig,
    )

    defaults: dict[str, Any] = Field(
        default_factory=dict,
    )

    errors: dict[str, BPMNError] = Field(
    default_factory=dict,
    )

    processes: dict[str, BPMNProcess]


#
# Activity DTOs
#


class HttpRequest(BaseModel):
    service: str

    method: str

    endpoint: str

    body: dict[str, Any] = Field(
        default_factory=dict,
    )

    retry: RetryPolicy | None = None

    timeout: TimeoutPolicy | None = None

    output_mappings: list[MappingItem] = Field(
        default_factory=list,
    )

    variables: dict[str, Any] = Field(
        default_factory=dict,
    )
