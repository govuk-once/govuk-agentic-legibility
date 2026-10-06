"""
BPMN XML parser - Converts BPMN XML into BPMNDefinition objects
"""

import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from bpmn.temporal_engine.bpmn_model import (
    BPMNDefinition,
    BPMNError,
    BPMNProcess,
    BoundaryEvent,
    CallActivity,
    CallActivityMappings,
    ContractField,
    EndEvent,
    ExclusiveGateway,
    FormDefinition,
    FormField,
    HttpServiceDefinition,
    IntermediateCatchEvent,
    MappingDefinition,
    MappingItem,
    MessageDefinition,
    NotificationDefinition,
    ProcessContract,
    RetryPolicy,
    ScriptTask,
    SendTask,
    SequenceFlow,
    ServiceTask,
    StartEvent,
    TimeoutPolicy,
    UserTask,
    WorkflowMetadata,
)
from bpmn.temporal_engine.process_registry import (
    PROCESS_REGISTRY,
)

logger = logging.getLogger(__name__)

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}

META_NS = {
    "meta": "urn:durable-workflow:metadata:v1",
}


# ---------------------------
# Generic Helpers
# ---------------------------

def parse_bool(
    value: str | None,
    default: bool = False,
) -> bool:
    if value is None:
        return default

    return value.lower() == "true"


def parse_mapping_items(
    items: list[dict],
) -> list[MappingItem]:
    return [
        MappingItem(**item)
        for item in items
    ]

# ---------------------------
# Process-Level Parsing
# ---------------------------

def parse_process_metadata(
    process_el: ET.Element,
) -> WorkflowMetadata | None:

    extensions = process_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return None

    workflow_meta = extensions.find(
        "meta:workflowMetadata",
        META_NS,
    )

    if workflow_meta is None:
        return None

    return WorkflowMetadata(
        name=workflow_meta.attrib.get(
            "name",
            "",
        ),
        version=workflow_meta.attrib.get(
            "version",
            "1.0.0",
        ),
    )


def parse_process_contract(
    process_el: ET.Element,
) -> ProcessContract | None:

    extensions = process_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return None

    contract = extensions.find(
        "meta:processContract",
        META_NS,
    )

    if contract is None:
        return None

    def build_fields(
        tag: str,
    ) -> list[ContractField]:

        return [
            ContractField(
                name=field.attrib["name"],
                type=field.attrib.get(
                    "type",
                ),
                required=parse_bool(
                    field.attrib.get(
                        "required",
                    ),
                ),
            )
            for field in contract.findall(
                tag,
                META_NS,
            )
        ]

    return ProcessContract(
        inputs=build_fields(
            "meta:input",
        ),
        outputs=build_fields(
            "meta:output",
        ),
    )


def parse_errors(
    root: ET.Element,
) -> dict[str, BPMNError]:

    return {
        error.attrib["id"]: BPMNError(
            id=error.attrib["id"],
            name=error.attrib.get(
                "name",
                error.attrib["id"],
            ),
        )
        for error in root.findall(
            "bpmn:error",
            BPMN_NS,
        )
    }

# ---------------------------
# Extension Parsing
# ---------------------------

def parse_extension_elements(
    node_el: ET.Element,
) -> dict[str, object]:

    metadata: dict[str, object] = {}

    extensions = node_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return metadata

    #
    # taskHandler
    #

    task_handler = extensions.find(
        "meta:taskHandler",
        META_NS,
    )

    if task_handler is not None:
        metadata["taskHandler"] = {
            "type": task_handler.attrib.get(
                "type",
            ),
        }

    #
    # form
    #

    form = extensions.find(
        "meta:form",
        META_NS,
    )

    if form is not None:

        fields = []

        for field in form.findall(
            "meta:field",
            META_NS,
        ):

            field_data = {
                key: value
                for key, value in field.attrib.items()
            }

            if "required" in field_data:
                field_data["required"] = parse_bool(
                    field_data["required"],
                )

            #
            # BPMN -> Python naming
            #

            if "sourceVariable" in field_data:
                field_data["source_variable"] = field_data.pop(
                    "sourceVariable",
                )

            #
            # options
            #

            field_data["options"] = [
                {
                    "value": option.attrib["value"],
                    "label": (option.text or "").strip(),
                }
                for option in field.findall(
                    "meta:option",
                    META_NS,
                )
            ]

            #
            # file constraints
            #

            constraints = field.find(
                "meta:fileConstraints",
                META_NS,
            )

            if constraints is not None:

                field_data["file_constraints"] = {
                    "max_size": (
                        int(
                            constraints.attrib[
                                "maxSize"
                            ]
                        )
                        if "maxSize"
                        in constraints.attrib
                        else None
                    ),
                    "allowed_types": (
                        constraints.attrib.get(
                            "allowedTypes",
                        )
                    ),
                }

            fields.append(
                field_data,
            )

        metadata["form"] = {
            "title": form.attrib.get(
                "title",
            ),
            "fields": fields,
        }

    #
    # process/call-activity mappings
    #

    metadata["inputs"] = [
        dict(item.attrib)
        for item in extensions.findall(
            "meta:input",
            META_NS,
        )
    ]

    metadata["outputs"] = [
        dict(item.attrib)
        for item in extensions.findall(
            "meta:output",
            META_NS,
        )
    ]

    #
    # http service
    #

    service = extensions.find(
        "meta:httpService",
        META_NS,
    )

    if service is not None:

        service_data: dict[str, object] = {
            "service": service.attrib.get(
                "service",
                "default",
            ),
            "method": service.attrib.get(
                "method",
            ),
            "endpoint": service.attrib.get(
                "endpoint",
            ),
            "inputs": [
                dict(item.attrib)
                for item in service.findall(
                    "meta:input",
                    META_NS,
                )
            ],
            "outputs": [
                dict(item.attrib)
                for item in service.findall(
                    "meta:output",
                    META_NS,
                )
            ],
        }

        retry = service.find(
            "meta:retry",
            META_NS,
        )

        if retry is not None:
            service_data["retry"] = dict(
                retry.attrib,
            )

        timeout = service.find(
            "meta:timeout",
            META_NS,
        )

        if timeout is not None:
            service_data["timeout"] = dict(
                timeout.attrib,
            )

        metadata["httpService"] = service_data

    #
    # mapping task
    #

    mapping = extensions.find(
        "meta:mapping",
        META_NS,
    )

    if mapping is not None:

        metadata["mapping"] = {
            "inputs": [
                dict(item.attrib)
                for item in mapping.findall(
                    "meta:input",
                    META_NS,
                )
            ],
            "outputs": [
               dict(item.attrib)
                for item in mapping.findall(
                    "meta:output",
                    META_NS,
                )
            ],
        }

    #
    # call activity validation flags
    #

    validate_inputs = extensions.find(
        "meta:validateInputs",
        META_NS,
    )

    if validate_inputs is not None:

        metadata["validateInputs"] = parse_bool(
            validate_inputs.attrib.get(
                "enabled",
            ),
        )

    validate_outputs = extensions.find(
        "meta:validateOutputs",
        META_NS,
    )

    if validate_outputs is not None:

        metadata["validateOutputs"] = parse_bool(
            validate_outputs.attrib.get(
                "enabled",
            ),
        )

    #
    # notification
    #

    notification = extensions.find(
        "meta:notification",
        META_NS,
    )

    if notification is not None:

        metadata["notification"] = {
            "channel": notification.attrib.get(
                "channel",
            ),
            "outputs": [
                dict(item.attrib)
                for item in notification.findall(
                    "meta:output",
                    META_NS,
                )
            ],
        }

    #
    # send task message
    #

    message = extensions.find(
        "meta:message",
        META_NS,
    )

    if message is not None:

        text_el = message.find(
            "meta:text",
            META_NS,
        )

        metadata["message"] = {
            "title": message.attrib.get(
                "title",
            ),
            "severity": message.attrib.get(
                "severity",
            ),
            "text": (
                text_el.text.strip()
                if text_el is not None
                and text_el.text
                else None
            ),
        }

    return metadata

# ---------------------------
# Node Parsers
# ---------------------------

def parse_user_task(
    el: ET.Element,
) -> UserTask:

    metadata = parse_extension_elements(
        el,
    )

    form = None

    if "form" in metadata:

        form_data = metadata["form"]

        form = FormDefinition(
            title=form_data.get(
                "title",
            ),
            fields=[
                FormField(**field)
                for field in form_data.get(
                    "fields",
                    [],
                )
            ],
        )

    return UserTask(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        metadata=metadata,
        form=form,
    )


def parse_service_task(
    el: ET.Element,
) -> ServiceTask:

    metadata = parse_extension_elements(
        el,
    )

    http_service = None

    if "httpService" in metadata:

        service = metadata["httpService"]

        http_service = HttpServiceDefinition(
            service=service["service"],
            method=service["method"],
            endpoint=service["endpoint"],
            inputs=parse_mapping_items(
                service.get(
                    "inputs",
                    [],
                )
            ),
            outputs=parse_mapping_items(
                service.get(
                    "outputs",
                    [],
                )
            ),
            retry=(
                RetryPolicy(
                    **service["retry"],
                )
                if "retry" in service
                else None
            ),
            timeout=(
                TimeoutPolicy(
                    **service["timeout"],
                )
                if "timeout" in service
                else None
            ),
        )

    return ServiceTask(
        id=el.attrib["id"],
        name=el.attrib.get(
            "name",
        ),
        metadata=metadata,
        http_service=http_service,
    )


def parse_script_task(
    el: ET.Element,
) -> ScriptTask:

    metadata = parse_extension_elements(
        el,
    )

    handler_type = (
        metadata.get(
            "taskHandler",
            {},
        ).get(
            "type",
        )
    )

    if handler_type not in {
        None,
        "mapping",
        "notification",
        "validation",
    }:
        raise ValueError(
            f"Unsupported task handler type: {handler_type}"
        )

    mapping = None

    if "mapping" in metadata:
        mapping = MappingDefinition(
            inputs=parse_mapping_items(
                metadata["mapping"].get(
                    "inputs",
                    [],
                )
            ),
            outputs=parse_mapping_items(
                metadata["mapping"].get(
                    "outputs",
                    [],
                )
            ),
        )

    notification = None

    if "notification" in metadata:

        notification_metadata = metadata[
            "notification"
        ]

        notification = NotificationDefinition(
            channel=notification_metadata[
                "channel"
            ],
            outputs=parse_mapping_items(
                notification_metadata.get(
                    "outputs",
                    [],
                )
            ),
        )

    return ScriptTask(
        id=el.attrib["id"],
        name=el.attrib.get(
            "name",
        ),
        metadata=metadata,
        task_handler_type=handler_type,
        notification=notification,
        mapping=mapping,
    )


def parse_send_task(
    el: ET.Element,
) -> SendTask:

    metadata = parse_extension_elements(
        el,
    )

    message = None

    if "message" in metadata:
        message = MessageDefinition(
            **metadata["message"],
        )

    return SendTask(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        metadata=metadata,
        message=message,
    )


def parse_call_activity(
    el: ET.Element,
) -> CallActivity:

    metadata = parse_extension_elements(
        el,
    )

    return CallActivity(
        id=el.attrib["id"],
        name=el.attrib.get(
            "name",
        ),
        called_element=el.attrib[
            "calledElement"
        ],
        metadata=metadata,
        mappings=CallActivityMappings(
            inputs=parse_mapping_items(
                metadata.get(
                    "inputs",
                    [],
                )
            ),
            outputs=parse_mapping_items(
                metadata.get(
                    "outputs",
                    [],
                )
            ),
            validate_inputs=metadata.get(
                "validateInputs",
                False,
            ),
            validate_outputs=metadata.get(
                "validateOutputs",
                False,
            ),
        ),
    )


def parse_end_event(
    el: ET.Element,
) -> EndEvent:

    error_ref = None

    error_event = el.find(
        "bpmn:errorEventDefinition",
        BPMN_NS,
    )

    if error_event is not None:
        error_ref = error_event.attrib.get(
            "errorRef",
        )

    return EndEvent(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        error_ref=error_ref,
    )


def parse_boundary_event(
    el: ET.Element,
) -> BoundaryEvent:

    error_event = el.find(
        "bpmn:errorEventDefinition",
        BPMN_NS,
    )

    return BoundaryEvent(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        attached_to_ref=el.attrib[
            "attachedToRef"
        ],
        error_ref=(
            error_event.attrib.get(
                "errorRef",
            )
            if error_event is not None
            else None
        ),
        cancel_activity=parse_bool(
            el.attrib.get(
                "cancelActivity",
            ),
            True,
        ),
    )


def parse_intermediate_catch_event(
    el: ET.Element,
) -> IntermediateCatchEvent | None:

    timer_def = el.find(
        "bpmn:timerEventDefinition",
        BPMN_NS,
    )

    if timer_def is None:
        return None

    duration = timer_def.find(
        "bpmn:timeDuration",
        BPMN_NS,
    )

    if duration is None or not duration.text:
        return None

    return IntermediateCatchEvent(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        duration=duration.text.strip(),
    )


def parse_exclusive_gateway(
    el: ET.Element,
) -> ExclusiveGateway:

    return ExclusiveGateway(
        id=el.attrib["id"],
        name=el.attrib.get("name"),
        default_flow=el.attrib.get(
            "default",
        ),
    )

# ---------------------------
# Flow Parsing
# ---------------------------

def parse_sequence_flows(
    process_el: ET.Element,
) -> dict[str, SequenceFlow]:

    flows: dict[str, SequenceFlow] = {}

    #
    # Parse sequence flows
    #

    for el in process_el.findall(
        "bpmn:sequenceFlow",
        BPMN_NS,
    ):

        condition = None

        condition_el = el.find(
            "bpmn:conditionExpression",
            BPMN_NS,
        )

        if (
            condition_el is not None
            and condition_el.text
        ):
            condition = (
                condition_el.text.strip()
            )

        flow = SequenceFlow(
            id=el.attrib["id"],
            source_ref=el.attrib[
                "sourceRef"
            ],
            target_ref=el.attrib[
                "targetRef"
            ],
            condition=condition,
        )

        flows[flow.id] = flow

    #
    # Mark gateway default routes
    #

    for gateway in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):

        default_flow = gateway.attrib.get(
            "default",
        )

        if (
            default_flow
            and default_flow in flows
        ):
            flows[
                default_flow
            ].is_default = True

    return flows

# ---------------------------
# Process & Definition
# ---------------------------

def parse_process(
    process_el: ET.Element,
) -> BPMNProcess:

    process_id = process_el.attrib["id"]

    nodes = {}
    start_event = None

    workflow_metadata = parse_process_metadata(
        process_el,
    )

    process_contract = parse_process_contract(
        process_el,
    )

    #
    # Start Events
    #

    for el in process_el.findall(
        "bpmn:startEvent",
        BPMN_NS,
    ):
        node = StartEvent(
            id=el.attrib["id"],
            name=el.attrib.get(
                "name",
            ),
        )

        nodes[node.id] = node
        start_event = node.id

    #
    # User Tasks
    #

    for el in process_el.findall(
        "bpmn:userTask",
        BPMN_NS,
    ):
        node = parse_user_task(
            el,
        )

        nodes[node.id] = node

    #
    # Service Tasks
    #

    for el in process_el.findall(
        "bpmn:serviceTask",
        BPMN_NS,
    ):
        node = parse_service_task(
            el,
        )

        nodes[node.id] = node

    #
    # Script Tasks
    #

    for el in process_el.findall(
        "bpmn:scriptTask",
        BPMN_NS,
    ):
        node = parse_script_task(
            el,
        )

        nodes[node.id] = node

    #
    # Send Tasks
    #

    for el in process_el.findall(
        "bpmn:sendTask",
        BPMN_NS,
    ):
        node = parse_send_task(
            el,
        )

        nodes[node.id] = node

    #
    # Call Activities
    #

    for el in process_el.findall(
        "bpmn:callActivity",
        BPMN_NS,
    ):
        node = parse_call_activity(
            el,
        )

        nodes[node.id] = node

    #
    # Exclusive Gateways
    #

    for el in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):
        node = parse_exclusive_gateway(
            el,
        )

        nodes[node.id] = node

    #
    # End Events
    #

    for el in process_el.findall(
        "bpmn:endEvent",
        BPMN_NS,
    ):
        node = parse_end_event(
            el,
        )

        nodes[node.id] = node

    #
    # Intermediate Catch Events
    #

    for el in process_el.findall(
        "bpmn:intermediateCatchEvent",
        BPMN_NS,
    ):
        node = parse_intermediate_catch_event(
            el,
        )

        if node is not None:
            nodes[node.id] = node

    #
    # Boundary Events
    #

    for el in process_el.findall(
        "bpmn:boundaryEvent",
        BPMN_NS,
    ):
        node = parse_boundary_event(
            el,
        )

        nodes[node.id] = node

    #
    # Sequence Flows
    #

    flows = parse_sequence_flows(
        process_el,
    )

    if start_event is None:
        raise ValueError(
            f"Process '{process_id}' contains no start event"
        )

    logger.info(
        "Parsed process %s: %s nodes, %s flows",
        process_id,
        len(nodes),
        len(flows),
    )

    return BPMNProcess(
        id=process_id,
        start_event=start_event,
        workflow_metadata=workflow_metadata,
        process_contract=process_contract,
        variables={},
        nodes=nodes,
        flows=flows,
    )


def parse_process_file(
    path: Path,
) -> BPMNProcess:

    root = ET.parse(
        path,
    ).getroot()

    process_el = root.find(
        "bpmn:process",
        BPMN_NS,
    )

    if process_el is None:
        raise ValueError(
            f"No process found in {path}"
        )

    return parse_process(
        process_el,
    )


def parse_bpmn_file(
    path: str | Path,
) -> BPMNDefinition:

    root = ET.parse(path).getroot()

    definition_id = root.attrib.get(
        "id",
        "workflow",
    )

    processes = {
        process.id: process
        for process in (
            parse_process(process_el)
            for process_el in root.findall(
                "bpmn:process",
                BPMN_NS,
            )
        )
    }

    if not processes:
        raise ValueError(
            "No BPMN process found",
        )

    entry_process = next(
        iter(processes.values())
    )

    version = (
        entry_process.workflow_metadata.version
        if entry_process.workflow_metadata
        else "1.0.0"
    )

    errors = parse_errors(
        root,
    )

    logger.info(
        "Parsed BPMN definition %s (%s process(es))",
        definition_id,
        len(processes),
    )

    return BPMNDefinition(
        schema="bpmn/0.1",
        id=definition_id,
        version=version,
        entry=entry_process.id,
        errors=errors,
        processes=processes,
        process_registry=PROCESS_REGISTRY
    )