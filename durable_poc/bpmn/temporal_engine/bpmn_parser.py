"""
BPMN XML parser.

Converts BPMN XML into BPMNDefinition objects
for execution by the Temporal BPMN interpreter.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from bpmn.temporal_engine.bpmn_model import (
    BPMNDefinition,
    BPMNProcess,
    BPMNError,
    BoundaryEvent,
    CallActivity,
    CallActivityMappings,
    ContractField,
    EndEvent,
    ExclusiveGateway,
    FormDefinition,
    FormField,
    HttpServiceDefinition,
    ManualTask,
    MappingItem,
    ParallelGateway,
    ProcessContract,
    RetryPolicy,
    ScriptTask,
    SequenceFlow,
    ServiceTask,
    StartEvent,
    TimeoutPolicy,
    UserTask,
    ValidationRule,
    WorkflowExecutorConfig,
    WorkflowMetadata,
    IntermediateCatchEvent,
    NotificationDefinition,
    MappingDefinition,
)

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}

META_NS = {
    "meta": "urn:durable-workflow:metadata:v1",
}

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

    return ProcessContract(
        inputs=[
            ContractField(
                name=x.attrib["name"],
                type=x.attrib.get("type"),
                required=(
                    x.attrib.get(
                        "required",
                        "false",
                    ).lower()
                    == "true"
                ),
            )
            for x in contract.findall(
                "meta:input",
                META_NS,
            )
        ],
        outputs=[
            ContractField(
                name=x.attrib["name"],
                type=x.attrib.get("type"),
                required=(
                    x.attrib.get(
                        "required",
                        "false",
                    ).lower()
                    == "true"
                ),
            )
            for x in contract.findall(
                "meta:output",
                META_NS,
            )
        ],
    )

def parse_bpmn_file(
    path: str | Path,
) -> BPMNDefinition:

    tree = ET.parse(path)

    root = tree.getroot()

    definition_id = root.attrib.get("id", "workflow")

    processes: dict[str, BPMNProcess] = {}

    for process_el in root.findall(
        "bpmn:process",
        BPMN_NS,
    ):
        process = parse_process(
            process_el,
        )

        processes[process.id] = process

    if not processes:
        raise ValueError("No BPMN process found")

    first_process = next(iter(processes.values()))

    version = "1.0.0"

    if first_process.workflow_metadata:
        version = first_process.workflow_metadata.version

    errors = parse_errors(root)

    print(f"Parsed BPMN definition {definition_id}: {len(processes)} process(es)")

    return BPMNDefinition(
        schema="bpmn/0.1",
        id=definition_id,
        version=version,
        entry=first_process.id,
        executor=WorkflowExecutorConfig(),
        processes=processes,
        errors=errors,
    )

def parse_errors(
    root: ET.Element,
) -> dict[str, BPMNError]:

    errors = {}

    for err in root.findall(
        "bpmn:error",
        BPMN_NS,
    ):
        error = BPMNError(
            id=err.attrib["id"],
            name=err.attrib.get(
                "name",
                err.attrib["id"],
            ),
        )

        errors[error.id] = error

    return errors

def parse_process(
    process_el: ET.Element,
) -> BPMNProcess:

    process_id = process_el.attrib["id"]

    nodes = {}

    flows = {}

    start_event = None

    workflow_metadata = parse_process_metadata(
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
            name=el.attrib.get("name"),
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

        node = UserTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=metadata,
            form=form,
        )

        nodes[node.id] = node

    #
    # Service Tasks
    #

    for el in process_el.findall(
        "bpmn:serviceTask",
        BPMN_NS,
    ):
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
                inputs=[
                    MappingItem(**x)
                    for x in service.get(
                        "inputs",
                        [],
                    )
                ],
                outputs=[
                    MappingItem(**x)
                    for x in service.get(
                        "outputs",
                        [],
                    )
                ],
                retry=(
                    RetryPolicy(**service["retry"])
                    if "retry" in service
                    else None
                ),
                timeout=(
                    TimeoutPolicy(**service["timeout"])
                    if "timeout" in service
                    else None
                ),
            )

        node = ServiceTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=metadata,
            http_service=http_service,
        )

        nodes[node.id] = node

    #
    # Script Tasks
    #

    for el in process_el.findall(
        "bpmn:scriptTask",
        BPMN_NS,
    ):
        metadata = parse_extension_elements(
            el,
        )

        mapping=(
            MappingDefinition(
                inputs=[
                    MappingItem(**x)
                    for x in metadata["mapping"].get(
                        "inputs",
                        [],
                    )
                ],
                outputs=[
                    MappingItem(**x)
                    for x in metadata["mapping"].get(
                        "outputs",
                        [],
                    )
                ],
            )
            if "mapping" in metadata
            else None
        )

        handler_type = (
            metadata.get("taskHandler", {})
            .get("type")
        )

        if handler_type not in {
            None,
            "validation",
            "mapping",
            "notification",
        }:
            raise ValueError(
                f"Unsupported task handler type: {handler_type}"
            )

        node = ScriptTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=metadata,
            task_handler_type=handler_type,
            mapping=mapping,
            notification=(
                NotificationDefinition(
                    **metadata["notification"]
                )
                if "notification" in metadata
                else None
            ),
            validation_rules=[
                ValidationRule(**rule)
                for rule in metadata.get(
                    "validationRules",
                    [],
                )
            ],
        )

        nodes[node.id] = node

    #
    # Manual Tasks
    #

    for el in process_el.findall(
        "bpmn:manualTask",
        BPMN_NS,
    ):
        node = ManualTask(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            metadata=parse_extension_elements(
                el,
            ),
        )

        nodes[node.id] = node

    #
    # Call Activities
    #

    for el in process_el.findall(
        "bpmn:callActivity",
        BPMN_NS,
    ):
        metadata = parse_extension_elements(el)

        node = CallActivity(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            called_element=el.attrib["calledElement"],
            metadata=metadata,
            mappings=CallActivityMappings(
                inputs=[
                    MappingItem(**x)
                    for x in metadata.get(
                        "inputs",
                        [],
                    )
                ],
                outputs=[
                    MappingItem(**x)
                    for x in metadata.get(
                        "outputs",
                        [],
                    )
                ],
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

        nodes[node.id] = node

    #
    # Exclusive Gateways
    #

    for el in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):
        node = ExclusiveGateway(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            default_flow=el.attrib.get("default"),
        )

        nodes[node.id] = node

    #
    # Parallel Gateways
    #

    for el in process_el.findall(
        "bpmn:parallelGateway",
        BPMN_NS,
    ):
        node = ParallelGateway(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
        )

        nodes[node.id] = node

    #
    # End Events
    #

    for el in process_el.findall(
        "bpmn:endEvent",
        BPMN_NS,
    ):
        error_ref = None

        error_def = el.find(
            "bpmn:errorEventDefinition",
            BPMN_NS,
        )

        if error_def is not None:
            error_ref = error_def.attrib.get(
                "errorRef",
            )

        node = EndEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            error_ref=error_ref,
        )


        nodes[node.id] = node

    #
    # Timer Events
    #

    for el in process_el.findall(
        "bpmn:intermediateCatchEvent",
        BPMN_NS,
    ):
        timer_def = el.find(
            "bpmn:timerEventDefinition",
            BPMN_NS,
        )

        if timer_def is None:
            continue

        duration = timer_def.find(
            "bpmn:timeDuration",
            BPMN_NS,
        )

        if duration is None or not duration.text:
            continue

        node = IntermediateCatchEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            duration=duration.text.strip(),
        )


        nodes[node.id] = node

    #
    # Boundary Events
    #

    for el in process_el.findall(
        "bpmn:boundaryEvent",
        BPMN_NS,
    ):
        error_ref = None

        err = el.find(
            "bpmn:errorEventDefinition",
            BPMN_NS,
        )

        cancel_activity=(
            el.attrib.get(
                "cancelActivity",
                "true",
            ).lower()
            == "true"
        )

        if err is not None:
            error_ref = err.attrib.get("errorRef")

        node = BoundaryEvent(
            id=el.attrib["id"],
            name=el.attrib.get("name"),
            attached_to_ref=el.attrib["attachedToRef"],
            error_ref=error_ref,
            cancel_activity=cancel_activity,
        )

        nodes[node.id] = node

    #
    # Sequence Flows
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

        if condition_el is not None and condition_el.text:
            condition = condition_el.text.strip()

        flow = SequenceFlow(
            id=el.attrib["id"],
            source_ref=el.attrib["sourceRef"],
            target_ref=el.attrib["targetRef"],
            condition=condition,
        )

        flows[flow.id] = flow

    #
    # Default Gateway Routes
    #

    for gateway in process_el.findall(
        "bpmn:exclusiveGateway",
        BPMN_NS,
    ):
        default_flow = gateway.attrib.get("default")

        if default_flow and default_flow in flows:
            flows[default_flow].is_default = True

    process_validation_rules = []

    extensions = process_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is not None:

        rules = extensions.find(
            "meta:validationRules",
            META_NS,
        )

        if rules is not None:
            process_validation_rules = [
                ValidationRule(**rule.attrib)
                for rule in rules.findall(
                    "meta:rule",
                    META_NS,
                )
            ]

    process_contract = parse_process_contract(
        process_el,
    )

    if start_event is None:
        raise ValueError(f"Process '{process_id}' contains no start event")

    print(f"Parsed process {process_id}: {len(nodes)} nodes, {len(flows)} flows")

    return BPMNProcess(
        id=process_id,
        start_event=start_event,
        workflow_metadata=workflow_metadata,
        process_contract=process_contract,
        validation_rules=process_validation_rules,
        variables={},
        nodes=nodes,
        flows=flows,
    )


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


def parse_extension_elements(
    node_el: ET.Element,
) -> dict:

    metadata: dict = {}

    extensions = node_el.find(
        "bpmn:extensionElements",
        BPMN_NS,
    )

    if extensions is None:
        return metadata

    #
    # taskHandler
    #

    handler = extensions.find(
        "meta:taskHandler",
        META_NS,
    )

    if handler is not None:
        metadata["taskHandler"] = {
            "type": handler.attrib.get(
                "type",
            )
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

            field_data = dict(
                field.attrib,
            )

            options = []

            for option in field.findall(
                "meta:option",
                META_NS,
            ):
                options.append(
                    {
                        "value": option.attrib["value"],
                        "label": (option.text or "").strip(),
                    }
                )

            field_data["options"] = options

            if "sourceVariable" in field.attrib:
                field_data["source_variable"] = (
                    field.attrib["sourceVariable"]
                )

            field_data.pop("sourceVariable", None)

            validation = field.find(
                "meta:validation",
                META_NS,
            )

            if validation is not None:
                field_data["validation"] = dict(
                    validation.attrib,
                )

            constraints = field.find(
                "meta:fileConstraints",
                META_NS,
            )

            if constraints is not None:
                field_data["fileConstraints"] = dict(
                    constraints.attrib,
                )

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
    # mappings
    #

    metadata["inputs"] = [
        dict(x.attrib)
        for x in extensions.findall(
            "meta:input",
            META_NS,
        )
    ]

    metadata["outputs"] = [
        dict(x.attrib)
        for x in extensions.findall(
            "meta:output",
            META_NS,
        )
]

    #
    # httpService
    #

    service = extensions.find(
        "meta:httpService",
        META_NS,
    )

    if service is not None:
        metadata["httpService"] = {
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
                dict(x.attrib)
                for x in service.findall(
                    "meta:input",
                    META_NS,
                )
            ],
            "outputs": [
                dict(x.attrib)
                for x in service.findall(
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
            metadata["httpService"]["retry"] = dict(retry.attrib)

        timeout = service.find(
            "meta:timeout",
            META_NS,
        )

        if timeout is not None:
            metadata["httpService"]["timeout"] = dict(timeout.attrib)

    #
    # mapping
    #

    mapping = extensions.find(
        "meta:mapping",
        META_NS,
    )

    if mapping is not None:
        metadata["mapping"] = {
            "inputs": [
                dict(x.attrib)
                for x in mapping.findall(
                    "meta:input",
                    META_NS,
                )
            ],
            "outputs": [
                dict(x.attrib)
                for x in mapping.findall(
                    "meta:output",
                    META_NS,
                )
            ],
        }

    #
    # manual review
    #

    review = extensions.find(
        "meta:manualReview",
        META_NS,
    )

    if review is not None:
        metadata["manualReview"] = dict(review.attrib)

    #
    # validation
    #

    validate_inputs = extensions.find(
    "meta:validateInputs",
    META_NS,
    )

    if validate_inputs is not None:
        metadata["validateInputs"] = (
            validate_inputs.attrib.get(
                "enabled",
                "false",
            ).lower()
            == "true"
        )

    validate_outputs = extensions.find(
        "meta:validateOutputs",
        META_NS,
    )

    if validate_outputs is not None:
        metadata["validateOutputs"] = (
            validate_outputs.attrib.get(
                "enabled",
                "false",
            ).lower()
            == "true"
        )

    rules = extensions.find(
        "meta:validationRules",
        META_NS,
    )

    if rules is not None:
        metadata["validationRules"] = [
            dict(rule.attrib)
            for rule in rules.findall(
                "meta:rule",
                META_NS,
            )
        ]

    #
    # notification
    #

    notification = extensions.find(
        "meta:notification",
        META_NS,
    )

    if notification is not None:
        metadata["notification"] = dict(
            notification.attrib,
        )

    return metadata
