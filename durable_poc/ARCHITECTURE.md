# Architecture

## Overview

The `durable_poc` application is a two-layer system designed for durable, structured workflow execution paired with a real-time conversational interface:

1. **Executor layer** (`src/`) — A deterministic, durable Finite State Machine (FSM) interpreter running inside Temporal. It accepts a JSON workflow definition (`SFSMDefinition`) and executes it step by step across nested process call stacks, suspending at human-in-the-loop input states and resuming when structured input is submitted via Temporal Updates.

2. **Agent & UI layer** (`agent/` & `chat.py`) — A conversational front-end powered by an LLM (Claude via AWS Bedrock) using the Strands Agents framework, surfaced via a FastAPI WebSocket application. The agent acts strictly as a silent intent parser—translating natural language into structured inputs expected by the executor—while Temporal remains the single source of truth for execution state.

The core research question: **can an LLM agent faithfully execute a strictly-defined process while providing natural language UX — without hallucinating steps, skipping states, or inventing options outside the definition?** Temporal is the integrity guardrail; the agent can only advance the workflow by submitting valid tokens through the executor's update validator.


```

┌──────────────────────────────────────────────────────────┐
│             User (Browser / HTML JS Frontend)            │
└────────────────────────┬─────────────────────────────────┘
│ WebSockets (ws://localhost:7860/ws)
┌────────────────────────▼─────────────────────────────────┐
│  chat.py — FastAPI Web Server                            │
│    ├── Silent NLU Intent Parsing via WorkflowAgent       │
│    └── Background Event Stream (Transcript & Schema UI)  │
└────────────────────────┬─────────────────────────────────┘
│ async call
┌────────────────────────▼─────────────────────────────────┐
│  agent/agent.py — WorkflowAgent                          │
│    Strands Agent with @tool closures                     │
│    Maintains session_state (HATEOAS continuation)        │
└──────────┬─────────────────────────────┬─────────────────┘
│ httpx                       │ Temporal gRPC
┌──────────▼──────────┐     ┌───────────▼─────────────────┐
│  Workflow Server     │     │  Temporal Server             │
│  (localhost:8080)    │     │  (localhost:7233)            │
│  Serves JSON defs    │     │                             │
└─────────────────────┘     │  ┌─────────────────────┐    │
│  │  SFSMInterpreter    │    │
│  │  (Workflow)          │    │
│  └─────────────────────┘    │
└─────────────────────────────┘

```

---

## Executor Layer (`src/`)

### `src/model.py` — Schema Models

Pydantic models that parse and validate JSON workflow definitions into an object graph. The top-level model is `SFSMDefinition`, which contains:

- `schema_`: Schema version identifier (aliased from `schema`, e.g. `"sfsm/0.2"`)
- `id`: Workflow logical identifier (e.g. `"dvla.change_of_address"`)
- `version`: Semantic version string
- `entry`: Name of the starting entry process
- `executor`: Configuration for Temporal execution (ID templates, timeouts, continue-as-new thresholds)
- `processes`: Map of process names to `Process` definition objects

Each `Process` has a `start` state ID, initial `vars`, and a `states` map. States are structured model types:

| State type | Purpose |
|---|---|
| `InputState` | Suspends execution and exposes a schema for human input with optional timeouts and retry routes. |
| `OutputState` | Emits a transcript entry to audit logs or dispatches external notifications via activities. |
| `CallState` | Executes HTTP API requests via Temporal activities with capture projections and error catches. |
| `ChoiceState` | Evaluates predicate rules against runtime context to branch execution. |
| `AssignState` | Mutates variable context (including date math like `now_plus` and integer `add` operations). |
| `InvokeState` | Pushes a sub-process stack frame onto the workflow call stack, binding inputs and catch routes. |
| `WaitState` | Durably sleeps for an ISO 8601 duration string (e.g., `PT5M`, `PT5D`). |
| `EndState` | Pops the stack frame, returning control and outputs to invoker states or finalizing the workflow. |

### `src/context.py` — Runtime State

Dataclasses representing the interpreter's mutable runtime context:

- **`InterpreterState`** — The full execution state: a stack of `StackFrame`s, a transcript list, a step counter, and environment dict. Serialized cleanly across Temporal Continue-As-New cycles.
- **`StackFrame`** — One frame on the process call stack: `process_id`, `state_id`, `vars` (frame scope), and an optional `invoker_state` reference.
- **`TranscriptEntry`** — Timestamped audit entry emitted by `OutputState` execution.
- **`AwaitingInput`** — Published via query when a workflow suspends: contains `token`, `prompt`, `schema`, resolved `options`, and optional `timeout_seconds`.
- **`InputSubmission`** — Payload submitted via Temporal Update: `token` (for verification) and structured `value`.

### `src/interpreter.py` — The Workflow Execution Loop

`SFSMInterpreter` is a `@workflow.defn` class. Its `run` method executes a deterministic step loop:

1. Validates definition dicts using `SFSMDefinition`.
2. Initialises the call stack (or resumes from `InterpreterState` after Continue-As-New).
3. Loops while stack frames exist, resolving current step context (evaluating frame variables, environment variables, step numbers, and `__now__` ISO timestamps).
4. Handles `InputState`: sets an input token (`tkn_{step}`), resolves options/prompts via `interpolate()` and `resolve_path()`, publishes `AwaitingInput` via query, and awaits an `asyncio.Event` (or a timeout duration).
5. Handles `InvokeState` / `EndState`: manages sub-process navigation by pushing/popping `StackFrame`s onto `self.state.frames` and passing returned variables safely back into parent scopes via `set_path()`.
6. Delegates non-deterministic operations (`CallState`, `OutputState`) to Temporal activities.

Key Temporal primitives used:

- **Update** (`submit_input`): Synchronous input entry point. A `_validate_input` validator checks schema types and regex constraints before state transitions.
- **Query** (`awaiting`, `transcript`): Exposes state safely without mutating execution state.
- **Continue-As-New**: Automatically serializes state and restarts workflow histories when Temporal suggests history truncation.

### `src/paths.py` — Path Resolution & Expression Utilities

Utility functions powering context traversal and expression evaluation:

- `resolve_path(context, "a.b.c")` — Dot-path traversal into dicts and indexed lists.
- `set_path(context, "a.b", val)` — Dot-path variable mutation.
- `interpolate(template, context)` — Interpolates `{{path.to.var}}` placeholders.
- `resolve_dict(data, context)` — Recursively evaluates `{"$": "path"}` reference maps.
- `parse_duration("PT5M")` — Parses ISO 8601 durations into `timedelta` objects.

### `src/predicates.py` — Condition Evaluator

Evaluates branching logic via `evaluate(condition, context)`. Operators include `eq`, `lt`, `lte`, `gt`, `gte`, `is_true`, `is_false`, `not_empty`, `and`, `or`, `not`, `before_now`, and `contains`. All logic uses structural recursion against context dictionaries without string `eval()`.

### `src/activities.py` — External Integrations

Out-of-sandbox Temporal activities:

- **`http_call(CallParams)`** — Issues HTTP requests via `httpx.AsyncClient` to underlying microservices (e.g., DVLA, Post Office) and projects captured fields out of response bodies/headers. Retries on 5xx/429 status codes via `RetryableHttpError`.
- **`notify(NotifyParams)`** — Handles external communication channels like email or SMS (mocked via structured logging).

### `src/errors.py` — Error Taxonomy

- `DefinitionError` — Schema or state reference errors.
- `ApplicationError` — Base exception for activity boundary errors.
- `RetryableHttpError` — Transient HTTP failures triggering Temporal retries.
- `ValidationError` — Non-retryable API constraint violations.
- `InputValidationError` — Synchronous validation error raised in update handlers.

### `src/worker.py` — Worker Bootstrap

Entry point: `python -m src.worker`. Connects to Temporal at `localhost:7233`, registers `SFSMInterpreter` alongside `http_call` and `notify` activities, and polls the `sfsm-queue` task queue.

### `src/demo.py` — Terminal CLI (Legacy)

An interactive terminal loop that drives a workflow execution directly via Temporal queries and updates. This was the original front-end before the agent layer; it requires the user to enter raw structured values.

---

## Agent & UI Layer (`agent/` & `chat.py`)

### `agent/tools.py` — Agent Tool Integrations

Pure async functions that bridge between the agent, external API endpoints, and Temporal:

| Function | Purpose | Target |
|---|---|---|
| `get_workflow_definition(...)` | Retrieves JSON definition schemas by numeric ID | Workflow Server (HTTP) |
| `start_workflow(...)` | Fetches definition schema and starts a new Temporal execution | Both |
| `list_active_workflows(...)` | Queries active running `SFSMInterpreter` executions | Temporal (gRPC) |
| `get_workflow_state(...)` | Resolves workflow handle, description status, `awaiting`, and `transcript` | Temporal (gRPC) |
| `submit_input(...)` | Submits input updates synchronously and returns updated state snapshot | Temporal (gRPC) |

- `start_workflow` accepts only a numeric `workflow_id` (not a raw definition), fetching the schema internally to prevent the LLM from fabricating or altering workflow JSON.
- `submit_input` follows the HATEOAS pattern: after submitting an update, it immediately queries and returns the newly resulting workflow state so the agent context is refreshed in a single round trip.

### `agent/agent.py` — WorkflowAgent Architecture

Composes the Bedrock LLM model (`anthropic.claude-sonnet-4-6`) with tool execution closures:

- **Lazy Connection Binding**: Temporal (`_get_temporal_client`) and HTTP (`_get_http_client`) clients connect lazily on first execution to ensure gRPC binding to the active event loop (such as FastAPI/uvicorn).
- **Silent NLU Persona (`agent/prompts/system.txt`)**: System instructions strictly direct the LLM to act as a silent intent parsing engine. The agent's task is solely to inspect user natural language, resolve missing or contextually implied values, and trigger tools. It **never** formats conversational filler or prompt text for display.
- **Strict JSON Type Coercion (`_coerce_value`)**: Normalizes LLM tool call arguments to conform to schema requirements before submission to Temporal:
  - `kind: "boolean"` — Coerces string variants (`"yes"`, `"y"`, `"sure"`, `"confirm"`) into primitive boolean `True`/`False`.
  - `kind: "string"` — Strips escaped string literal quotes and validates regex patterns.
  - `kind: "select_one"` — When options resolve to full dictionary objects (e.g. UPRN address maps or organ donor choices), coerces string choices into the **entire matching dictionary object**.
  - `kind: "file_ref"` or `kind: "object"` — Parses incoming file metadata strings into standard dictionary payloads.
- **HATEOAS Context Injection**: `build_contextual_prompt()` appends current `session_state` (`workflow_id`, `token`, awaiting prompt, and schema) directly into the user message prompt, eliminating reliance on LLM conversation memory.

### `chat.py` — WebSockets Web Interface

A standalone FastAPI server driving a GOV.UK-styled web interface:

- **WebSocket Communication (`/ws`)**: Handles real-time bi-directional transport between the browser client and the backend server.
- **Direct Event Stream Renderer (`stream_background_events`)**: A dedicated background polling loop that queries `get_workflow_state` every 0.5s:
  - **Transcript Entries**: Reads `OutputState` transcript additions directly from Temporal history and streams them as clean assistant messages to the client.
  - **Awaiting Prompts**: Detects active input tokens and streams the raw schema prompt text directly to the UI (once per token).
  - **Dynamic Option Generation (`get_options_from_state`)**: Inspects the schema kind (`boolean`, `enum`, `select_one`) and extracts human-readable option labels, sending an `options` JSON payload to render frontend buttons.
- **Silent Agent Ingestion**: The WebSocket text handler forwards user input to `agent_instance.respond()`. The LLM's conversational text return is ignored; its output is delivered exclusively through Temporal tool calls (`submit_input`, `start_workflow`).

---

## Data Flow: A Complete Turn


```

User Input          FastAPI (chat.py)          WorkflowAgent           Temporal Engine
│                        │                        │                        │
├─ "Change my address" ─►│                        │                        │
│                        ├─ respond(msg) ────────►│                        │
│                        │                        ├─ start_workflow(id=1)─►│
│                        │                        │                        ├─ Start SFSMInterpreter
│                        │                        │                        ├─ Execute to InputState
│                        │                        │                        └─ Publish AwaitingInput
│                        │◄─ Stream Transcript ───┼────────────────────────┤
│◄─ Render Prompt/Btns ──┤   & Schema Prompt      │                        │
│                        │                        │                        │
├─ Click "Yes" ─────────►│                        │                        │
│                        ├─ respond("Yes") ──────►│                        │
│                        │                        ├─ submit_input(...) ───►│
│                        │                        │  (coerces "Yes"->True) │├─ Validate Update
│                        │                        │                        ├─ Advance FSM Loop
│                        │                        │                        └─ Reach next InputState
│                        │◄─ Stream Next Prompt ──┼────────────────────────┤
│◄─ Render New Step ─────┤   & Updated Options    │                        │

```

1. **Service Initiation**: User submits *"I want to change the address on my driving licence"*.
2. **Intent Parsing**: `chat.py` passes the message to `WorkflowAgent.respond()`. The LLM calls `get_workflow_definition(workflow_id=1)` followed by `start_workflow(workflow_id=1)`.
3. **Workflow Execution**: Temporal launches `SFSMInterpreter`. It evaluates `confirm_intent` (`InputState`), publishes token `tkn_1` via query, and halts at `workflow.wait_condition`.
4. **Direct Stream Rendering**: The background loop in `chat.py` polls `get_workflow_state`, detects token `tkn_1`, and pushes the raw prompt (*"Would you like to proceed with changing the address on your driving licence?"*) and binary options `["Yes", "No"]` straight to the WebSocket.
5. **Input Submission**: User clicks **Yes**. `chat.py` passes `"Yes"` to the agent.
6. **Type Coercion & Update**: The agent invokes `submit_input(workflow_id="...", token="tkn_1", value=true)`. `_coerce_value` ensures the value is passed as boolean `True`. Temporal's `_validate_input` validator checks the payload and unblocks the execution loop.
7. **Sub-process Execution**: The engine transitions through `branch_intent`, invokes `driver_details` sub-process frame onto the stack, executes `http_call` activity to query DVLA records (`/app/dvla/v1/driver-summary`), and halts at `confirm_driver_details`.
8. **UI State Update**: `stream_background_events` detects the updated transcript and newly generated token `tkn_2`, pushing the interpolated driver details text and new option choices to the user.

---

## Key Design Decisions

### 1. Dual-Path Architecture (Agent Intent Parser + Direct System Renderer)
To guarantee strict regulatory compliance and eliminate LLM text hallucinations, text rendering is completely decoupled from LLM text generation:
- The **Agent Layer** is strictly an NLU intent parser and tool caller. It maps user natural language into structured API inputs.
- The **System Engine** reads output transcript entries and schema prompt strings directly from Temporal queries, streaming them straight to the UI.

### 2. Synchronous Temporal Updates for Input Validation
Inputs are passed via Temporal Updates (`submit_input`) rather than asynchronous Signals. Updates execute synchronously within the workflow loop; if a token is stale, a pattern check fails, or a type is incorrect, Temporal rejects the update immediately. The agent receives this rejection in the same turn and can request corrections without desynchronizing workflow state.

### 3. HATEOAS Continuation Pattern
Every tool execution returns a self-describing state object (`awaiting` token, schema, options, and transcript). The agent does not rely on conversation memory to track workflow progress—the authoritative state is reinjected into the context prompt on every turn.

### 4. Dynamic Option Generation & Type Coercion
User options are built dynamically from the active input schema (e.g. `select_one` option tables or boolean flags). `_coerce_value` acts as a defensive buffer between the LLM tool call output and Temporal's strict validation handlers, automatically mapping dictionary objects, string primitives, and booleans.

### 5. Hierarchical Process Frame Stack
Sub-processes (`driver_details`, `photo_update`, `signature_update`, `select_address`, `organ_donation`, `address_update`, `finalisation`) are managed via an internal `StackFrame` stack within a single Temporal workflow execution. This preserves variable isolation, supports return value mapping, enables continue-as-new serialization, and avoids the operational complexity of child workflow signals.

---

## Test Architecture

| Test file | Scope | Dependencies |
|---|---|---|
| `test_pure.py` | `paths.py` and `predicates.py` — pure functions | None |
| `test_workflow.py` | Full interpreter execution against local Temporal dev server | `temporal` CLI binary |
| `test_agent_tools.py` | Tool functions with `FakeTemporalClient` and `httpx.MockTransport` | None |
| `test_agent.py` | `WorkflowAgent` composition, session state updates, contextual prompt building | None |
| `test_chat.py` | FastAPI WebSocket endpoints, message rendering, option generation | None |

---

## Entry Points

| Command | Entry Point File | Description |
|---|---|---|
| `python -m src.worker` | `src/worker.py` | **Temporal Worker**: Connects to Temporal (`localhost:7233`) and polls task queue `sfsm-queue`. Must be running for any workflow execution. |
| `python -m chat` | `chat.py` | **FastAPI Web App & WebSocket UI**: Launches the web application on `http://localhost:7860`. Serves the GOV.UK frontend and manages real-time agent/workflow streaming. |
| `python -m src.demo` | `src/demo.py` | **Terminal CLI (Legacy)**: Interactive terminal CLI driving workflows directly via raw Temporal queries/updates without the agent layer. |

```
