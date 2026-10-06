"""
Temporal BPMN workflow interpreter.

Supported BPMN elements:

- StartEvent
- UserTask
- ServiceTask
- ScriptTask
- SendTask
- ExclusiveGateway
- IntermediateCatchEvent
- CallActivity
- BoundaryEvent
- EndEvent

Supported metadata:

- meta:form
- meta:httpService
- meta:mapping
- meta:notification
- meta:message
- meta:taskHandler

TODO:
- Continue-As-New
- OpenTelemetry spans
- ParallelGateway
"""

import asyncio
from copy import deepcopy
from datetime import timedelta
from typing import Any

from temporalio import workflow

from bpmn.temporal_engine.bpmn_model import (
    BPMNDefinition,
    BPMNProcess,
    CallActivity,
    EndEvent,
    ExclusiveGateway,
    ScriptTask,
    ServiceTask,
    SendTask,
    StartEvent,
    IntermediateCatchEvent,
    UserTask,
    MappingItem,
    ProcessContract,
)

from src.context import (
    AwaitingInput,
    InputSubmission,
    InterpreterState,
    StackFrame,
)

from src.paths import (
    interpolate,
    parse_duration,
    resolve_path,
    set_path,
    resolve_literal,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

class BPMNRuntimeError(Exception):
    """
    BPMN business error.

    Used to route execution through BPMN
    boundary events.
    """

    def __init__(
        self,
        error_ref: str,
    ) -> None:
        super().__init__(
            error_ref,
        )

        self.error_ref = error_ref


@workflow.defn
class BPMNInterpreter:
    def __init__(self) -> None:

        self.definition: BPMNDefinition | None = None

        self.state = InterpreterState()

        self._awaiting_input: AwaitingInput | None = None

        self._received_input: Any = None

        self._input_ready_event = asyncio.Event()
    #
    # Helpers
    #

    def _handle_boundary_error(
        self,
        process: BPMNProcess,
        task_id: str,
        frame: StackFrame,
        error_ref: str,
    ) -> bool:
        """
        Route execution via a BPMN boundary event.

        Returns True if handled.
        """
        workflow.logger.info(
            f"Looking for boundary event "
            f"task={task_id} "
            f"error={error_ref}"
        )

        target = process.boundary_target(
            task_id,
            error_ref,
        )

        workflow.logger.info(
            f"Boundary target={target}"
        )

        if target is None:
            return False

        workflow.logger.warning(
            f"Boundary event triggered for "
            f"'{task_id}' "
            f"(error={error_ref})"
        )

        frame.state_id = target

        return True

    def _validate_contract(
        self,
        contract: ProcessContract | None,
        variables: dict[str, Any],
        mode: str,
    ) -> None:

        if contract is None:
            return

        fields = (
            contract.inputs
            if mode == "inputs"
            else contract.outputs
        )

        for field in fields:

            if not field.required:
                continue

            value = resolve_path(
                variables,
                field.name,
            )

            if value is None:
                raise RuntimeError(
                    f"Contract validation failed: "
                    f"{field.name}"
                )

    def _evaluate_expression(
        self,
        expression: str,
        variables: dict[str, Any],
    ) -> bool:

        try:
            context = deepcopy(
                variables,
            )

            context["true"] = True
            context["false"] = False
            context["null"] = None

            return bool(
                eval(
                    expression,
                    {},
                    context,
                )
            )

        except Exception as exc:
            raise RuntimeError(
                f"Failed evaluating BPMN expression '{expression}'"
            ) from exc

    def _apply_output_mappings(
        self,
        variables: dict[str, Any],
        outputs: list[MappingItem],
    ) -> None:

        for mapping in outputs:
            source = mapping.source

            target = mapping.target

            value = resolve_path(
                variables,
                source,
            )

            if value is None:
                value = resolve_literal(
                    source,
                )

            set_path(
                variables,
                target,
                value,
            )

    def _move_to_next_node(
        self,
        process: BPMNProcess,
        node_id: str,
        frame: StackFrame,
    ) -> None:

        next_node = process.get_single_next_node_id(
            node_id,
        )

        workflow.logger.info(f"Transition {process.id}:{node_id} -> {next_node}")

        frame.state_id = next_node

    def _record_activity(
        self,
        process_id: str,
        node: Any,
    ) -> None:

        self.state.activity_history.append(
            {
                "step": self.state.step_counter,
                "process_id": process_id,
                "id": node.id,
                "name": node.name,
                "type": node.__class__.__name__,
            }
        )

    #
    # Workflow Entry
    #

    @workflow.run
    async def run(
        self,
        definition_dict: dict[str, Any],
        initial_state: (InterpreterState | None) = None,
    ) -> dict[str, Any]:

        self.definition = BPMNDefinition.model_validate(
            definition_dict,
        )

        workflow.logger.info(
            f"Loaded BPMN definition {self.definition.id} v{self.definition.version}"
        )

        if initial_state:
            self.state = initial_state
            workflow.logger.info(
                f"Resuming workflow with {len(initial_state.frames)} frame(s)"
            )

        else:
            process = self.definition.processes[self.definition.entry]

            workflow.logger.info(f"Starting process {process.id}")

            self.state.frames.append(
                StackFrame(
                    process_id=process.id,
                    state_id=process.start_event,
                    vars=deepcopy(process.variables),
                )
            )

        while self.state.frames:
            await asyncio.sleep(0)

            self.state.step_counter += 1

            workflow.logger.info(f"Frame depth={len(self.state.frames)}")

            frame = self.state.frames[-1]

            process = self.definition.processes[frame.process_id]

            current_node = process.get_node(
                frame.state_id,
            )

            self._record_activity(
                process.id,
                current_node,
            )

            workflow.logger.info(
                f"[Step {self.state.step_counter}] "
                f"[{process.id}:{current_node.id}] "
                f"({type(current_node).__name__})"
            )

            #
            # StartEvent
            #

            if isinstance(
                current_node,
                StartEvent,
            ):
                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                continue

            #
            # UserTask
            #

            if isinstance(
                current_node,
                UserTask,
            ):
                workflow.logger.info(f"Waiting for user input at {current_node.id}")

                token = f"tkn_{self.state.step_counter}"

                if current_node.form is None:
                    raise RuntimeError(
                        f"UserTask '{current_node.id}' has no form definition"
                    )

                form = current_node.form

                self._awaiting_input = AwaitingInput(
                    token=token,
                    prompt=(form.title or current_node.name or current_node.id),
                    schema=form,
                    options=None,
                    timeout_seconds=None,
                    state_id=current_node.id,
                    state_type="UserTask",
                )

                self._received_input = None

                self._input_ready_event.clear()

                await workflow.wait_condition(lambda: self._input_ready_event.is_set())

                workflow.logger.info(f"Received user input for {current_node.id}")

                if not isinstance(
                    self._received_input,
                    dict,
                ):
                    raise RuntimeError(
                        f"UserTask '{current_node.id}' requires object input"
                    )

                for field in form.fields:
                    variable = field.variable

                    field_id = field.id

                    workflow.logger.info(f"Field mapping {field_id} -> {variable}")

                    if variable and field_id and field_id in self._received_input:
                        workflow.logger.info(f"Setting variable {variable}")

                        set_path(
                            frame.vars,
                            variable,
                            self._received_input[field_id],
                        )

                self._awaiting_input = None

                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                continue

            #
            # ScriptTask
            #

            if isinstance(
                current_node,
                ScriptTask,
            ):
                if current_node.task_handler_type == "mapping":
                    workflow.logger.info(f"Executing mapping task {current_node.id}")

                    if current_node.mapping is None:
                        raise RuntimeError(
                            f"Mapping task '{current_node.id}' "
                            f"has no mapping definition"
                        )

                    self._apply_output_mappings(
                        frame.vars,
                        current_node.mapping.outputs,
                    )

                    self._move_to_next_node(
                        process,
                        current_node.id,
                        frame,
                    )

                    continue

                if current_node.task_handler_type == "notification":

                    if current_node.notification is None:
                        raise RuntimeError(
                            f"Notification task '{current_node.id}' "
                            f"has no notification definition"
                        )

                    await workflow.execute_activity(
                        "send_notification",
                        {
                            "channel": current_node.notification.channel,
                            "variables": frame.vars,
                        },
                        start_to_close_timeout=timedelta(
                            seconds=30,
                        ),
                    )

                    for mapping in current_node.notification.outputs:

                        value = resolve_literal(
                            mapping.source,
                        )

                        set_path(
                            frame.vars,
                            mapping.target,
                            value,
                        )

                        workflow.logger.info(
                            "Notification output %s -> %s",
                            mapping.source,
                            mapping.target,
                        )

                    self._move_to_next_node(
                        process,
                        current_node.id,
                        frame,
                    )

                    continue

                raise RuntimeError(
                    f"Unsupported ScriptTask handler "
                    f"'{current_node.task_handler_type}'"
                )

            #
            # SendTask
            #

            if isinstance(
                current_node,
                SendTask,
            ):
                if current_node.message:

                    activity = self.state.activity_history[-1]

                    activity["title"] = interpolate(
                        current_node.message.title or "",
                        frame.vars,
                    )

                    activity["text"] = interpolate(
                        current_node.message.text or "",
                        frame.vars,
                    )

                    activity["severity"] = (
                        current_node.message.severity
                    )

                workflow.logger.info(
                    "Message task %s",
                    current_node.id,
                )

                if current_node.message:
                    workflow.logger.info(
                        "Message: %s",
                        current_node.message.title,
                    )

                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                continue

            #
            # ServiceTask
            #

            if isinstance(
                current_node,
                ServiceTask,
            ):
                workflow.logger.info(f"Executing ServiceTask {current_node.id}")

                handler = current_node.metadata.get(
                    "taskHandler",
                    {},
                ).get(
                    "type",
                )

                workflow.logger.info(f"Handler type: {handler}")

                if handler == "http":
                    service = current_node.http_service

                    if service is None:
                        raise RuntimeError(
                            f"ServiceTask '{current_node.id}' has no http_service"
                        )

                    endpoint = interpolate(
                        service.endpoint,
                        frame.vars,
                    )

                    request_payload = {}

                    for mapping in service.inputs:
                        workflow.logger.info(
                            f"Input mapping {mapping.source} -> {mapping.target}"
                        )

                        value = resolve_path(
                            frame.vars,
                            mapping.source,
                        )

                        set_path(
                            request_payload,
                            mapping.target,
                            value,
                        )

                    workflow.logger.info(f"HTTP {service.method} {endpoint}")

                    workflow.logger.info(f"Request payload: {request_payload}")

                    try:
                        retry_policy = RetryPolicy(
                            maximum_attempts=1,
                        )

                        if service.retry:
                            retry_policy = RetryPolicy(
                                maximum_attempts=service.retry.attempts,
                                initial_interval=timedelta(
                                    seconds=service.retry.backoff_seconds,
                                ),
                            )

                        result = await workflow.execute_activity(
                            "http_call",
                            {
                                "service": service.service,
                                "method": service.method,
                                "endpoint": endpoint,
                                "body": request_payload,
                                "retry": (
                                    service.retry.model_dump()
                                    if service.retry
                                    else None
                                ),
                                "timeout": (
                                    service.timeout.model_dump()
                                    if service.timeout
                                    else None
                                ),
                                "output_mappings": [
                                    mapping.model_dump()
                                    for mapping in service.outputs
                                ],
                                "variables": frame.vars,
                            },
                            start_to_close_timeout=timedelta(
                                minutes=5,
                            ),
                            retry_policy=retry_policy,
                        )

                    except ActivityError:
                        handled = self._handle_boundary_error(
                            process,
                            current_node.id,
                            frame,
                            "ApiFailure",
                        )

                        if handled:
                            continue

                        raise

                    workflow.logger.info(
                        f"HTTP activity completed for {current_node.id}"
                    )

                    for key, value in result.items():
                        set_path(
                            frame.vars,
                            key,
                            value,
                        )

                else:
                    raise RuntimeError(f"Unsupported task handler: {handler}")

                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                continue

            #
            # IntermediateCatchEvent
            #

            if isinstance(
                current_node,
                IntermediateCatchEvent,
            ):
                workflow.logger.info(f"Waiting on timer {current_node.duration}")

                await workflow.sleep(
                    parse_duration(
                        current_node.duration,
                    )
                )

                workflow.logger.info(f"Timer completed {current_node.id}")

                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                continue

            #
            # ExclusiveGateway
            #

            if isinstance(
                current_node,
                ExclusiveGateway,
            ):
                workflow.logger.info(f"Evaluating gateway {current_node.id}")

                outgoing = process.outgoing_flows(
                    current_node.id,
                )

                #
                # Gateway merge
                #
                if len(outgoing) == 1:
                    workflow.logger.info(f"Gateway merge {current_node.id}")

                    frame.state_id = outgoing[0].target_ref

                    continue

                matched = False

                for flow in outgoing:
                    if flow.condition is None:
                        continue

                    if self._evaluate_expression(
                        flow.condition,
                        frame.vars,
                    ):
                        workflow.logger.info(f"Gateway matched flow {flow.id}")

                        frame.state_id = flow.target_ref

                        matched = True

                        break

                if matched:
                    continue

                default_flow = next(
                    (f for f in outgoing if f.is_default),
                    None,
                )

                if default_flow:
                    workflow.logger.info(
                        f"Gateway taking default flow {default_flow.id}"
                    )

                    frame.state_id = default_flow.target_ref

                    continue

                raise RuntimeError(f"No matching path for gateway {current_node.id}")

            #
            # CallActivity
            #

            if isinstance(
                current_node,
                CallActivity,
            ):
                workflow.logger.info(
                    f"Invoking subprocess {current_node.called_element}"
                )

                process_path = self.definition.process_registry[
                        current_node.called_element
                    ]

                child_process_data = await workflow.execute_activity(
                    "load_process",
                    process_path,
                    start_to_close_timeout=timedelta(
                        seconds=30,
                    ),
                )

                child_process = BPMNProcess.model_validate(
                    child_process_data,
                )

                self.definition.processes[
                    child_process.id
                ] = child_process

                if child_process is None:
                    raise RuntimeError(
                        f"Process '{current_node.called_element}' not found"
                    )

                self._move_to_next_node(
                    process,
                    current_node.id,
                    frame,
                )

                child_vars = deepcopy(
                    child_process.variables,
                )

                for mapping in current_node.mappings.inputs:

                    value = resolve_path(
                        frame.vars,
                        mapping.source,
                    )

                    set_path(
                        child_vars,
                        mapping.target,
                        value,
                    )

                if current_node.mappings.validate_inputs:
                    self._validate_contract(
                        child_process.process_contract,
                        child_vars,
                        "inputs",
                    )

                child_frame = StackFrame(
                    process_id=child_process.id,
                    state_id=child_process.start_event,
                    vars=child_vars,
                    invoker_state=current_node.id,
                )

                self.state.frames.append(
                    child_frame,
                )

                workflow.logger.info(f"Pushed subprocess frame {child_process.id}")

                continue

            #
            # EndEvent
            #

            if isinstance(
                current_node,
                EndEvent,
            ):
                completed = self.state.frames.pop()

                workflow.logger.info(
                    f"Reached end event "
                    f"{completed.process_id}:"
                    f"{current_node.id} "
                    f"error_ref={current_node.error_ref}"
                )

                if current_node.error_ref:

                    if not self.state.frames:
                        raise BPMNRuntimeError(
                            current_node.error_ref,
                        )

                    parent_frame = self.state.frames[-1]

                    parent_process = self.definition.processes[
                        parent_frame.process_id
                    ]

                    call_activity = parent_process.get_node(
                        completed.invoker_state,
                    )

                    if isinstance(
                        call_activity,
                        CallActivity,
                    ):
                        handled = self._handle_boundary_error(
                            parent_process,
                            call_activity.id,
                            parent_frame,
                            current_node.error_ref,
                        )

                        if handled:
                            continue

                    raise BPMNRuntimeError(
                        current_node.error_ref,
                    )

                workflow.logger.info(
                    f"Process completed {completed.process_id}"
                )

                #
                # Returning from subprocess
                #

                if self.state.frames:

                    parent_frame = self.state.frames[-1]

                    parent_process = self.definition.processes[
                        parent_frame.process_id
                    ]

                    call_activity = parent_process.get_node(
                        completed.invoker_state,
                    )

                    if isinstance(
                        call_activity,
                        CallActivity,
                    ):

                        if call_activity.mappings.validate_outputs:

                            child_process = self.definition.processes[
                                completed.process_id
                            ]

                            self._validate_contract(
                                child_process.process_contract,
                                completed.vars,
                                "outputs",
                            )

                        for mapping in call_activity.mappings.outputs:

                            value = resolve_path(
                                completed.vars,
                                mapping.source,
                            )

                            set_path(
                                parent_frame.vars,
                                mapping.target,
                                value,
                            )

                    workflow.logger.info(
                        "Returning to parent process"
                    )

                    continue

                workflow.logger.info(
                    "Workflow completed"
                )

                return {
                    "process_id": completed.process_id,
                    "variables": completed.vars,
                }

            raise RuntimeError(
                f"Unsupported BPMN node type "
                f"{type(current_node).__name__}"
            )

    @workflow.update
    async def submit_input(
        self,
        msg: InputSubmission,
    ) -> None:

        workflow.logger.info(f"Input update received token={msg.token}")

        #
        # TODO:
        # Port validation logic from
        # SFSMInterpreter
        #

        if self._awaiting_input is None:
            raise ValueError("Workflow is not awaiting input")

        if msg.token != self._awaiting_input.token:
            raise ValueError("Invalid input token")

        workflow.logger.info(f"Input received token={msg.token}")

        self._received_input = msg.value

        self._input_ready_event.set()

    @workflow.query
    def awaiting(
        self,
    ) -> AwaitingInput | None:

        return self._awaiting_input

    @workflow.query
    def current_state_info(
        self,
    ) -> dict[str, Any] | None:

        if not self.state.frames:
            return None

        frame = self.state.frames[-1]

        return {
            "process_id": frame.process_id,
            "state_id": frame.state_id,
            "step": self.state.step_counter,
        }

    @workflow.query
    def evaluation_checkpoint(
        self,
    ) -> dict[str, Any]:

        return {
            "current_state": self.current_state_info(),
            "step_counter": self.state.step_counter,
            "frames": [
                {
                    "process_id": frame.process_id,
                    "state_id": frame.state_id,
                    "vars": frame.vars,
                }
                for frame in self.state.frames
            ],
        }

    @workflow.query
    def get_activity_history(
        self,
    ) -> list[dict[str, Any]]:

        return self.state.activity_history

    @workflow.query
    def current_variables(
        self,
    ) -> dict[str, Any]:


        if not self.state.frames:
            return {}

        return self.state.frames[-1].vars
