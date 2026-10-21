"""The durable workflow executor loop."""

import asyncio
from copy import deepcopy
import re
from typing import Any, NoReturn

from temporalio import workflow

# Inform Temporal to allow imports that might otherwise be deemed unsafe in the sandbox
with workflow.unsafe.imports_passed_through():
    import pydantic

    from src.context import (
        AwaitingInput,
        InputSubmission,
        InterpreterState,
        StackFrame,
        TranscriptEntry,
    )
    from src.errors import DefinitionError, InputValidationError
    from src.model import (
        InputState,
        InvokeState,
        SFSMDefinition,
    )
    from src.handlers import STATE_HANDLERS
    from opentelemetry import trace as otel_trace

_tracer = otel_trace.get_tracer(__name__)


@workflow.defn
class SFSMInterpreter:
    """Deterministic finite-state-machine interpreter running inside Temporal.

    Accepts a JSON workflow definition (``SFSMDefinition``) and executes it
    step-by-step across nested process call stacks, suspending at
    human-in-the-loop input states and resuming when structured input is
    submitted via Temporal Updates.

    Attributes:
        MAX_TRANSCRIPT_LENGTH: Hard cap on retained transcript entries.
        state: The mutable runtime execution state.
        definition: The parsed workflow definition, set during ``run()``.
        tracer: OpenTelemetry tracer shared with extracted state handlers.
    """

    MAX_TRANSCRIPT_LENGTH = 100

    def __init__(self) -> None:
        """Initialise interpreter signals and empty runtime state."""
        self.state = InterpreterState()
        self.definition: SFSMDefinition | None = None
        self.tracer = _tracer

        # State signals
        self._input_ready_event = asyncio.Event()
        self._awaiting_input: AwaitingInput | None = None
        self._received_input: Any | None = None
        self._timeout_triggered: bool = False

    @workflow.run
    async def run(
        self,
        definition_dict: dict[str, Any],
        initial_state: InterpreterState | None = None,
    ) -> Any:
        """Execute the workflow definition to completion.

        Validates the definition, initialises (or resumes) the call stack,
        then loops through states by dispatching to the handler registered
        for each state type until the stack is empty or an ``EndState``
        returns a result.

        Args:
            definition_dict: Raw JSON-serialisable workflow definition.
            initial_state: Optional checkpoint to resume from (used after
                Temporal Continue-As-New).

        Returns:
            The result dict produced by the root ``EndState``, or ``None``
            if the stack empties without an explicit end.

        Raises:
            DefinitionError: If the definition fails Pydantic validation or
                a referenced process/state is missing.
        """
        try:
            self.definition = SFSMDefinition.model_validate(definition_dict)
        except pydantic.ValidationError as e:
            workflow.logger.error(f"❌ Definition validation failed: {e}")
            raise DefinitionError(f"Invalid workflow definition: {e}") from e

        if initial_state:
            self.state = initial_state
            self._rehydrate_initial_state_invokers()
            workflow.logger.info(
                f"Resuming workflow from initial_state context with frames: {self.state.frames}"
            )
        else:
            entry_process = self.definition.processes.get(self.definition.entry)
            if not entry_process:
                raise DefinitionError(
                    f"Entry process '{self.definition.entry}' not found in processes definition"
                )

            initial_vars = entry_process.vars.copy()
            self.state.frames.append(
                StackFrame(
                    process_id=self.definition.entry,
                    state_id=entry_process.start,
                    vars=initial_vars,
                )
            )
            workflow.logger.info(
                f"Started workflow entry process '{self.definition.entry}' at state '{entry_process.start}' "
                f"with initial vars: {initial_vars}"
            )

        min_steps_between_can = 0
        if self.definition.executor.continue_as_new:
            min_steps_between_can = self.definition.executor.continue_as_new.get(
                "min_steps_between", 50
            )

        steps_this_run = 0

        while self.state.frames:
            # Yield control back to Temporal event loop to prevent event starvation
            await asyncio.sleep(0)

            if (
                workflow.info().is_continue_as_new_suggested()
                and steps_this_run >= min_steps_between_can
            ):
                workflow.logger.info("Executing Continue-As-New...")
                workflow.continue_as_new(definition_dict, self.state)

            self.state.step_counter += 1
            steps_this_run += 1
            frame = self.state.frames[-1]
            process = self.definition.processes.get(frame.process_id)
            if not process:
                raise DefinitionError(f"Process '{frame.process_id}' not found")

            current_state = process.states.get(frame.state_id)

            if not current_state:
                workflow.logger.error(
                    f"❌ State '{frame.state_id}' not found in process '{frame.process_id}'"
                )
                raise DefinitionError(
                    f"State {frame.state_id} not found in {frame.process_id}"
                )

            workflow.logger.info(
                f"[Step {self.state.step_counter}] [{frame.process_id}:{frame.state_id}] ({type(current_state).__name__})"
            )

            # Prepare deterministic context for this step (MUST use workflow.now())
            context = {
                "input": frame.vars.get("input", {}),
                "env": self.state.env,
                "workflow_id": workflow.info().workflow_id,
                "step": self.state.step_counter,
                "__now__": workflow.now().isoformat(),
            }
            context.update(frame.vars)

            handler = STATE_HANDLERS.get(type(current_state))
            if handler is None:
                raise DefinitionError(
                    f"No handler registered for {type(current_state).__name__}"
                )
            result = await handler(current_state, frame, context, self)
            if result is not None:
                return result

    @workflow.update
    async def submit_input(self, msg: InputSubmission) -> None:
        """Accept a validated input submission and unblock the waiting handler."""
        workflow.logger.info(f"📩 Input submitted via update: val={msg.value}")
        self._received_input = msg.value
        self._input_ready_event.set()

    def _raise_input_validation_error(
        self, msg: InputSubmission, *, code: str, message: str
    ) -> NoReturn:
        """Record an existing input-validation failure, then raise it unchanged."""
        awaiting = self._awaiting_input
        frame = self.state.frames[-1] if self.state.frames else None

        process_id = frame.process_id if frame else None
        state_id = awaiting.state_id if awaiting else (frame.state_id if frame else None)
        schema = awaiting.schema if awaiting else None
        schema_kind = schema.kind if schema else None

        assign_target = None
        if frame is not None and self.definition is not None:
            process = self.definition.processes.get(frame.process_id)
            current_state = process.states.get(frame.state_id) if process else None
            if isinstance(current_state, InputState):
                assign_target = current_state.assign

        attributes = {
            "temporalWorkflowID": workflow.info().workflow_id,
            "process_id": process_id,
            "state_id": state_id,
            "schema_kind": schema_kind,
            "assign_target": assign_target,
            "token": msg.token,
            "expected_token": awaiting.token if awaiting else None,
            "rejection_code": code,
            "rejection_message": message,
            "rejected_value_type": type(msg.value).__name__,
            "rejected_value": str(msg.value),
        }
        with _tracer.start_as_current_span(
            "interpreter.input_validation.rejected",
            attributes={key: value for key, value in attributes.items() if value is not None},
        ):
            pass

        workflow.logger.warning(
            f"❌ Rejected update ({code}): token={msg.token} value={msg.value!r}: {message}"
        )
        raise InputValidationError(message)

    @submit_input.validator
    def _validate_input(self, msg: InputSubmission) -> None:
        """Synchronously validate an input submission before it reaches the handler.

        Checks are performed in order: awaiting state, token match, then
        type- and kind-specific constraints (boolean, string with optional
        regex pattern, select_one/select_many option membership, and
        file_ref structure).

        Args:
            msg: The candidate input containing a token and value.

        Raises:
            InputValidationError: If any check fails, via
                ``_raise_input_validation_error``.
        """
        if not self._awaiting_input:
            self._raise_input_validation_error(
                msg, code="not_awaiting_input", message="Not awaiting input"
            )
        if msg.token != self._awaiting_input.token:
            self._raise_input_validation_error(
                msg,
                code="token_mismatch",
                message=f"Token mismatch. Expected {self._awaiting_input.token}",
            )

        schema = self._awaiting_input.schema
        kind = schema.kind
        val = msg.value

        if kind == "boolean" and not isinstance(val, bool):
            self._raise_input_validation_error(
                msg,
                code="expected_boolean",
                message=f"Expected boolean, received {type(val).__name__}",
            )
        if kind == "string" and not isinstance(val, str):
            self._raise_input_validation_error(
                msg,
                code="expected_string",
                message=f"Expected string, received {type(val).__name__}",
            )
        if (kind == "string" and schema.pattern and not re.match(schema.pattern, str(val))):
            self._raise_input_validation_error(
                msg,
                code="invalid_format",
                message=schema.invalid_message or "Invalid format",
            )

        if kind in ("select_one", "select_many"):
            options = (
                schema.options
                or self._awaiting_input.options
                or []
            )

            # Explicit integer index check
            if kind == "select_one" and isinstance(val, int):
                idx = val - 1
                if 0 <= idx < len(options):
                    return

            v_key = schema.value_key or "value"
            valid_values: list[Any] = []
            for opt in options:
                if isinstance(opt, dict):
                    valid_values.append(
                        opt.get(v_key, opt.get("uprn", opt.get("id", opt.get("value"))))
                    )
                else:
                    valid_values.append(getattr(opt, "value", opt))

            if kind == "select_one":
                if val not in valid_values and val not in options:
                    self._raise_input_validation_error(
                        msg,
                        code="invalid_selection",
                        message=f"Invalid selection: '{val}'. Please select a valid option.",
                    )

            if kind == "select_many":
                if not isinstance(val, list):
                    self._raise_input_validation_error(
                        msg,
                        code="expected_list",
                        message="Expected list of values for select_many",
                    )
                for item in val:
                    if isinstance(item, int):
                        idx = item - 1
                        if 0 <= idx < len(options):
                            continue
                    if item not in valid_values and item not in options:
                        self._raise_input_validation_error(
                            msg,
                            code="invalid_selection_item",
                            message=f"Invalid item '{item}' in selection list",
                        )

        if kind == "file_ref":
            # A supplied optional file is still a native file reference; only
            # the explicit optional skip is represented by null.
            if val is None and schema.allow_skip is True:
                return
            if not isinstance(val, dict) or "error" in val:
                self._raise_input_validation_error(
                    msg,
                    code="invalid_file_upload",
                    message="Invalid file upload. Please use the upload button.",
                )
            if not val.get("ref") or int(val.get("bytes", 0)) <= 0:
                self._raise_input_validation_error(
                    msg,
                    code="invalid_file_payload",
                    message="File payload missing valid reference or size.",
                )


    def _rehydrate_initial_state_invokers(self) -> None:
        """Replace serialised invoker state IDs with real InvokeState objects."""
        if self.definition is None:
            raise DefinitionError("Cannot rehydrate initial state without a definition")

        for index, frame in enumerate(self.state.frames):
            if frame.invoker_state is None or isinstance(
                frame.invoker_state, InvokeState
            ):
                continue
            if not isinstance(frame.invoker_state, str) or index == 0:
                raise DefinitionError(
                    "Invalid invoker reference for frame "
                    f"{frame.process_id}.{frame.state_id}"
                )

            parent = self.state.frames[index - 1]
            parent_process = self.definition.processes.get(parent.process_id)
            if parent_process is None:
                raise DefinitionError(
                    f"Parent process '{parent.process_id}' not found while "
                    "restoring checkpoint"
                )

            invoker = parent_process.states.get(frame.invoker_state)
            if not isinstance(invoker, InvokeState):
                raise DefinitionError(
                    f"Checkpoint invoker '{frame.invoker_state}' in process "
                    f"'{parent.process_id}' is not an InvokeState"
                )
            if invoker.process != frame.process_id:
                raise DefinitionError(
                    f"Checkpoint invoker '{frame.invoker_state}' targets "
                    f"'{invoker.process}', not '{frame.process_id}'"
                )
            frame.invoker_state = invoker

    @workflow.query
    def awaiting(self) -> AwaitingInput | None:
        """Return the current awaiting-input descriptor, or ``None``."""
        return self._awaiting_input

    @workflow.query
    def transcript(self) -> list[TranscriptEntry]:
        """Return the current transcript entries."""
        return self.state.transcript

    @workflow.query
    def current_state_info(self) -> dict[str, Any] | None:
        """Return a summary of the top-of-stack state for polling consumers.

        Returns:
            A dict with ``process_id``, ``state_id``, ``state_type``, and
            ``step``, or ``None`` if no frames remain.
        """
        if not self.state.frames:
            return None
        frame = self.state.frames[-1]
        process = (
            self.definition.processes.get(frame.process_id) if self.definition else None
        )
        state = process.states.get(frame.state_id) if process else None
        return {
            "process_id": frame.process_id,
            "state_id": frame.state_id,
            "state_name": state.name if state else None,
            "state_metadata": state.metadata if state else {},
            "state_type": type(state).__name__ if state else None,
            "step": self.state.step_counter,
        }

    @workflow.query
    def evaluation_checkpoint(self) -> dict[str, Any]:
        """Return a semantic snapshot of the current interpreter state for evals.

        This deliberately captures SFSM state rather than Temporal event history.
        ``invoker_state`` is represented by its state ID so a future loader can
        rehydrate it from the workflow definition instead of serialising the
        Pydantic state object itself.
        """
        frames: list[dict[str, Any]] = []
        for index, frame in enumerate(self.state.frames):
            frames.append(
                {
                    "process_id": frame.process_id,
                    "state_id": frame.state_id,
                    "vars": deepcopy(frame.vars),
                    "invoker_state_id": self._invoker_state_id(index),
                }
            )

        awaiting = None
        if self._awaiting_input is not None:
            awaiting = {
                "token": self._awaiting_input.token,
                "prompt": self._awaiting_input.prompt,
                "schema": self._awaiting_input.schema.model_dump(by_alias=True, exclude_none=True),
                "options": deepcopy(self._awaiting_input.options),
                "timeout_seconds": self._awaiting_input.timeout_seconds,
                "state_id": self._awaiting_input.state_id,
                "state_type": self._awaiting_input.state_type,
            }

        return {
            "schema_version": "sfsm-interpreter-checkpoint/0.1",
            "current_state": self.current_state_info(),
            "awaiting": awaiting,
            "interpreter_state": {
                "frames": frames,
                "transcript": [
                    {
                        "step": entry.step,
                        "timestamp": entry.timestamp,
                        "message": entry.message,
                    }
                    for entry in self.state.transcript
                ],
                "step_counter": self.state.step_counter,
                "env": deepcopy(self.state.env),
            },
        }

    def _invoker_state_id(self, frame_index: int) -> str | None:
        """Resolve a child frame's invoker to its state ID in the parent process."""
        frame = self.state.frames[frame_index]
        if frame.invoker_state is None or frame_index == 0 or self.definition is None:
            return None

        parent = self.state.frames[frame_index - 1]
        parent_process = self.definition.processes.get(parent.process_id)
        if parent_process is None:
            return None

        for state_id, candidate in parent_process.states.items():
            if candidate is frame.invoker_state or candidate == frame.invoker_state:
                return state_id
        return None
