# Architecture

## Overview

The `durable_poc` application is a two-layer system designed for durable, structured workflow execution paired with a real-time conversational interface and observable event tracing:

1. **Executor layer** (`src/`) — A deterministic, durable Finite State Machine (FSM) interpreter running inside Temporal. It accepts a JSON workflow definition (`SFSMDefinition`) and executes it step by step across nested process call stacks, suspending at human-in-the-loop input states and resuming when structured input is submitted via Temporal Updates.

2. **Agent & UI layer** (`agent/` & `chat.py`) — A conversational front-end powered by an LLM (Claude via AWS Bedrock) using the Strands Agents framework, surfaced via a FastAPI WebSocket application. The agent acts strictly as a silent intent parser—translating natural language into structured inputs expected by the executor—while Temporal remains the single source of truth for execution state.

The core research question: **can an LLM agent faithfully execute a strictly-defined process while providing natural language UX — without hallucinating steps, skipping states, or inventing options outside the definition?** Temporal is the integrity guardrail; the agent can only advance the workflow by submitting valid tokens through the executor's update validator.


```

┌─────────────────────────────────────────────────────────────────────────────────┐
│                      User Browser (Split-Screen Web UI)                         │
│   ┌──────────────────────────────────┬──────────────────────────────────────┐   │
│   │ Main Chat & Option Buttons       │ Real-Time Execution Trace Sidebar    │   │
│   └──────────────────────────────────┴──────────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                          │ WebSockets (ws://localhost:7860/ws)
┌────────────────────────────────────────▼────────────────────────────────────────┐
│  chat.py — FastAPI Web Server                                                   │
│    ├── Silent NLU Intent Parsing via WorkflowAgent                              │
│    ├── Background Event Stream (Transcript, Prompts, Options, Timeouts)        │
│    └── Real-time Trace Broadcaster (USER, AGENT, ENGINE, SYSTEM channels)       │
└────────────────────────┬────────────────────────────────────────────────────────┘
                          │ async call with on_trace callback
┌────────────────────────▼────────────────────────────────────────────────────────┐
│  agent/agent.py — WorkflowAgent                                                 │
│    Strands Agent with @tool closures & tool decision event emitter             │
│    Maintains session_state (HATEOAS continuation)                               │
└──────────┬─────────────────────────────┬────────────────────────────────────────┘
            │ httpx                       │ Temporal gRPC
┌──────────▼──────────┐     ┌───────────▼────────────────────────────────────────┐
│  Workflow Server    │     │  Temporal Server (localhost:7233)                  │
│  (localhost:8080)   │     │                                                    │
│  Serves JSON defs   │     │  ┌──────────────────────────────────────────────┐  │
└─────────────────────┘     │  │  SFSMInterpreter (Workflow Loop)             │  │
                            │  │   ├── StackFrames & Event Yields             │  │
                            │  │   └── Update Validator & State Queries       │  │
                            │  └──────────────────────┬───────────────────────┘  │
                            └─────────────────────────┼──────────────────────────┘
                                                      │ Activities
                                    ┌─────────────────▼──────────────────────────┐
                                    │ activities.py (http_call & notify)         │
                                    │  ├── SERVICE_ENV_MAP Routing               │
                                    │  └── Idempotency-Key Header Forwarding     │
                                    └────────────────────────────────────────────┘

```

---

## Executor Layer (`src/`)

### `src/model.py` — Schema Models

Pydantic models that parse and validate JSON workflow definitions into an object graph. The top-level model is `SFSMDefinition`, which contains:

* `schema_`: Schema version identifier (aliased from `schema`, e.g. `"sfsm/0.2"`)
* `id`: Workflow logical identifier (e.g. `"dvla.change_of_address"`)
* `version`: Semantic version string
* `entry`: Name of the starting entry process
* `executor`: Configuration for Temporal execution (ID templates, timeouts, continue-as-new thresholds)
* `processes`: Map of process names to `Process` definition objects

Each `Process` has a `start` state ID, initial `vars`, and a `states` map. States are structured model types:

| State type | Purpose |
|---|---|
| `InputState` | Suspends execution and exposes a schema for human input with optional timeouts and retry routes. |
| `OutputState` | Emits a transcript entry to audit logs or dispatches external notifications via activities. |
| `CallState` | Executes HTTP API requests via Temporal activities with capture projections, idempotency headers, and error catches. |
| `ChoiceState` | Evaluates predicate rules against runtime context to branch execution. |
| `AssignState` | Mutates variable context (including date math like `now_plus` and integer `add` operations). |
| `InvokeState` | Pushes a sub-process stack frame onto the workflow call stack, binding inputs and catch routes. |
| `WaitState` | Durably sleeps for an ISO 8601 duration string (e.g., `PT5M`, `PT14D`). |
| `EndState` | Pops the stack frame, returning control and outputs to invoker states or finalizing the workflow. |

### `src/context.py` — Runtime State

Dataclasses representing the interpreter's mutable runtime context:

* **`InterpreterState`**: The full execution state: a stack of `StackFrame`s, a transcript list, a step counter, and environment dict. Serialized cleanly across Temporal Continue-As-New cycles.
* **`StackFrame`**: One frame on the process call stack: `process_id`, `state_id`, `vars` (frame scope), and an optional `invoker_state` reference.
* **`TranscriptEntry`**: Timestamped audit entry emitted by `OutputState` execution or internal engine execution events (`[ENGINE LOG]`).
* **`AwaitingInput`**: Published via query when a workflow suspends: contains `token`, `prompt`, `schema`, resolved `options`, `timeout_seconds`, `state_id`, and `state_type`.
* **`InputSubmission`**: Payload submitted via Temporal Update: `token` (for verification) and structured `value`.

### `src/interpreter.py` — The Workflow Execution Loop

`SFSMInterpreter` is a `@workflow.defn` class. Its `run` method executes a deterministic step loop:

1. Validates definition dicts using `SFSMDefinition`.
2. Initialises the call stack (or resumes from `InterpreterState` after Continue-As-New).
3. Loops while stack frames exist, yielding control (`await asyncio.sleep(0)`) at the start of every iteration to prevent thread starvation during long synchronous state chains.
4. Handles `InputState`: sets an input token (`tkn_{step}`), resolves options/prompts via `interpolate()` and `resolve_path()`, publishes `AwaitingInput` via query, and awaits an `asyncio.Event` (or a timeout duration).
5. Handles `CallState`: interpolates `idempotency_key` against runtime context and dispatches `http_call` activity with `CallParams`. Logs `[ENGINE LOG]` execution events to the transcript.
6. Handles `InvokeState` / `EndState`: manages sub-process navigation by pushing/popping `StackFrame`s onto `self.state.frames` and passing returned variables safely back into parent scopes via `set_path()`. Raises `DefinitionError` if a requested process is missing.

Key Temporal primitives used:

* **Update** (`submit_input`): Synchronous input entry point. A `_validate_input` validator checks schema types and regex constraints before state transitions.
* **Query** (`awaiting`, `transcript`, `current_state_info`): Exposes state safely without mutating execution state.
* **Continue-As-New**: Automatically serializes state and restarts workflow histories when Temporal suggests history truncation.

### `src/paths.py` — Path Resolution & Expression Utilities

Utility functions powering context traversal and expression evaluation:

* `resolve_path(context, "a.b.c")`: Dot-path traversal into dicts and indexed lists.
* `set_path(context, "a.b", val)`: Dot-path variable mutation.
* `interpolate(template, context)`: Interpolates `{{path.to.var}}` placeholders.
* `resolve_dict(data, context)`: Recursively evaluates `{"$": "path"}` reference maps.
* `parse_duration("PT5M")`: Parses ISO 8601 durations into `timedelta` objects.

### `src/predicates.py` — Condition Evaluator

Evaluates branching logic via `evaluate(condition, context)`. Operators include `eq`, `lt`, `lte`, `gt`, `gte`, `is_true`, `is_false`, `not_empty`, `and`, `or`, `not`, `before_now`, and `contains`. All logic uses structural recursion against context dictionaries without string `eval()`. Symmetrically handles boolean string coercion for `is_false`.

### `src/activities.py` — External Integrations

Out-of-sandbox Temporal activities:

* **`http_call(CallParams)`**: Issues HTTP requests via `httpx.AsyncClient` to underlying microservices. Resolves base URLs using `SERVICE_ENV_MAP` (e.g. `DVLA_BASE`, `POSTOFFICE_BASE`) and raises `ValidationError` for unconfigured services. Attaches `Idempotency-Key` headers when supplied in `CallParams`. Retries on 5xx/429 status codes via `RetryableHttpError`.
* **`notify(NotifyParams)`**: Handles external communication channels like email or SMS (mocked via structured logging).

### `src/errors.py` — Error Taxonomy

* `DefinitionError`: Schema or state reference errors.
* `ApplicationError`: Base exception for activity boundary errors.
* `RetryableHttpError`: Transient HTTP failures triggering Temporal retries.
* `ValidationError`: Non-retryable API constraint or service configuration violations.
* `InputValidationError`: Synchronous validation error raised in update handlers.

### `src/telemetry.py` — OpenTelemetry Tracing Infrastructure

Provides span exporters, span processors, and provider factory functions for distributed tracing across both the chat/agent and Temporal worker processes. See the [Distributed Tracing](#distributed-tracing) section below for the full design.

* **`SessionSpanProcessor`**: A `SpanProcessor` that stamps a `session_id` attribute on every span. The session ID is set per WebSocket connection and allows grouping all traces from a single user session.
* **`FileSpanExporter`**: Appends spans as JSONL to a local file. Used for local development and debugging.
* **`S3SpanExporter`**: Batches spans in memory and flushes to S3 as JSONL objects. Keys use Hive-style partitioning (`{prefix}/year={y}/month={m}/day={d}/hour={h}/trace-{timestamp}.jsonl`) for direct compatibility with Athena, Glue crawlers, and Spark.
* **`create_agent_provider()`**: Builds a standard `TracerProvider` for the chat/agent process, with optional `SessionSpanProcessor` and exporter attachment.
* **`create_worker_provider()`**: Builds a `ReplaySafeTracerProvider` (via Temporal's `create_tracer_provider()`) for the worker process. This wrapper suppresses span creation during Temporal's deterministic workflow replay, preventing duplicate spans.

The S3 bucket name is resolved in order: explicit argument, `OTEL_EXPORT_S3_BUCKET` environment variable, or the AWS Systems Manager Parameter Store parameter `/durable_poc/temp_trace_bucket`. If none resolves, S3 export is silently disabled.

### `src/worker.py` — Worker Bootstrap

Entry point: `python -m src.worker`. Connects to Temporal at `localhost:7233`, registers `SFSMInterpreter` alongside `http_call` and `notify` activities, and polls the `sfsm-queue` task queue. Initialises a `ReplaySafeTracerProvider` and attaches a `_FilteredTracingInterceptor` to both the Temporal client and the worker (see [Distributed Tracing](#distributed-tracing)).

### `src/demo.py` — Terminal CLI (Legacy)

An interactive terminal loop that drives a workflow execution directly via Temporal queries and updates. This was the original front-end before the agent layer; it requires the user to enter raw structured values.

---

## Agent & UI Layer (`agent/` & `chat.py`)

### `agent/tools.py` — Agent Tool Integrations

Pure async functions that bridge between the agent, external API endpoints, and Temporal:

| Function | Purpose | Target |
|---|---|---|
| `get_workflow_definition(...)` | Retrieves JSON definition schemas by numeric ID | Workflow Server (HTTP) |
| `start_workflow(...)` | Fetches definition schema and starts a new Temporal execution with randomized UUID suffix | Both |
| `list_active_workflows(...)` | Queries active running `SFSMInterpreter` executions | Temporal (gRPC) |
| `get_workflow_state(...)` | Resolves workflow handle, status, `awaiting`, and `transcript` | Temporal (gRPC) |
| `submit_input(...)` | Submits input updates synchronously and returns updated state snapshot | Temporal (gRPC) |

### `agent/agent.py` — WorkflowAgent Architecture

Composes the Bedrock LLM model (`anthropic.claude-sonnet-4-6`) with tool execution closures and event trace callbacks:

* **Lazy Connection Binding**: Temporal (`_get_temporal_client`) and HTTP (`_get_http_client`) clients connect lazily on first execution.
* **Trace Callback Propagation (`on_trace`)**: Emits structured trace events (`AGENT`, `SYSTEM`, `ENGINE`) whenever Bedrock selects a tool or executes an API call, streaming trace details directly to the UI sidebar.
* **Silent NLU Persona (`agent/prompts/system.txt`)**: System instructions strictly direct the LLM to act as a silent intent parsing engine. The agent's task is solely to inspect user natural language, resolve missing or contextually implied values, and trigger tools. It **never** formats conversational filler or prompt text for display.
* **Strict JSON Type Coercion (`_coerce_value`)**: Normalizes LLM tool call arguments  to conform to schema requirements before submission to Temporal:
  * `kind: "boolean"`: Coerces string variants (`"yes"`, `"true"`, `"1"`) or raw strings into primitive boolean `True`/`False`.
  * `kind: "string"`: Strips escaped string literal quotes and validates regex patterns.
  * `kind: "select_one"`: When options resolve to full dictionary objects (e.g. UPRN address maps or organ donor choices), coerces string choices into the **entire matching dictionary object**.
  * `kind: "file_ref"` or `kind: "object"`: Parses incoming file metadata strings into standard dictionary payloads.
* **HATEOAS Context Injection (`build_contextual_prompt()`)**: Appends current `session_state` (`workflow_id`, `token`, awaiting prompt, and schema) directly into the user message prompt, eliminating reliance on LLM conversation memory.

### `chat.py` — WebSockets Web Interface & Event Trace

A standalone FastAPI server driving a split-screen GOV.UK-styled web interface:

* **WebSocket Communication (`/ws`)**: Handles real-time bi-directional transport between the browser client and the backend server(`message`, `options`, `trace`, `timeout`, `completed`, `active_workflows`).
* **Direct Event Stream Renderer (`stream_background_events`)**: A dedicated background polling loop that queries `get_workflow_state`
  * **Transcript Entries**: Streams `OutputState` messages to the main chat column.
  * **Engine Events**: Intercepts `[ENGINE LOG]` transcript entries and routes them directly to the Trace Sidebar.
  * **Dynamic Option Buttons**: Inspects the schema kind (`boolean`, `enum`, `select_one`) and extracts human-readable option labels, sending an `options` JSON payload to render frontend buttons.
  * **Timeout Display**: Pushes `timeout_seconds` to render a top-level warning badge.
  * **Completion State**: Detects terminal execution states and renders a completion banner.
* **Resume Workflow Handler (`refresh_active_workflows`)**: Populates an active workflow picker on page load, allowing users to resume executions directly without LLM interaction.

---

## Data Flow: A Complete Turn


```

User Input             FastAPI (chat.py)              WorkflowAgent               Temporal Engine
    │                          │                            │                            │
    ├─ "Change my address" ───►│                            │                            │
    │                          ├─ emit_trace("USER")        │                            │
    │                          ├─ respond(msg, on_trace) ──►│                            │
    │                          │                            ├─ start_workflow(id=1) ────►│
    │                          │◄─ on_trace("AGENT", tool) ─┤                            ├─ Start SFSMInterpreter
    │                          │◄─ on_trace("ENGINE", id) ──┤                            ├─ Execute to InputState
    │                          │                            │                            └─ Publish AwaitingInput
    │◄─ Render Prompt/Btns ────┤◄─ Stream Transcript ───────┴────────────────────────────┤
    │◄─ Update Trace Sidebar ──┤   & Engine Logs                                         │
    │                          │                                                         │
    ├─ Click "Yes" ───────────►│                                                         │
    │                          ├─ respond("Yes") ──────────►                             │
    │                          │                            ├─ submit_input(...) ───────►│
    │                          │                            │  (coerces "Yes"->True)     ├─ Validate Update
    │                          │◄─ on_trace("ENGINE", ok) ──┤                            ├─ Advance FSM Loop
    │                          │                            │                            └─ Reach next InputState
    │◄─ Render Next Step ──────┤◄─ Stream Next Prompt ──────┴────────────────────────────┤

```

1. **User Action**: User submits *"I need to change the address on my driving licence"*.
2. **Intent Parsing**: `chat.py` records a `USER` trace and invokes `WorkflowAgent.respond()`. Bedrock calls `start_workflow(workflow_id=1)`, emitting `AGENT` and `SYSTEM` trace events via `on_trace`.
3. **Workflow Execution**: Temporal launches `SFSMInterpreter`. It yields to the event loop, enters `driver_details` sub-process frame (`[ENGINE LOG]`), executes `http_call` activity with `DVLA_BASE` routing and idempotency headers (`[ENGINE LOG]`), and halts at `InputState` (`tkn_1`).
4. **Direct Stream Rendering**: The background loop in `chat.py` polls `get_workflow_state`, routes `[ENGINE LOG]` entries to the sidebar, and pushes the prompt (*"Would you like to proceed...?"*) and binary options `["Yes", "No"]` to the main chat view.
5. **Input Submission**: User clicks **Yes**. `_coerce_value` converts `"Yes"` to boolean `True`. `submit_input` sends the update to Temporal, where `_validate_input` validates the token and type synchronously.
6. **UI State Update**: Execution advances to the next step, streaming updated options, transcript text, and sidebar trace events in real time.

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

## Distributed Tracing

### Overview

The application uses [OpenTelemetry](https://opentelemetry.io/) (OTEL) to produce distributed traces that link a user's WebSocket message through the agent, across the Temporal gRPC boundary, and into the workflow interpreter and its activities. Traces are exported to S3 as Hive-partitioned JSONL for analysis via Athena or similar tools.

There are two independent tracing systems in the application. The **UI sidebar trace** (`on_trace` callbacks → WebSocket → browser) is a real-time display for the end user and is unrelated to OTEL. The **OTEL traces** described here are for backend observability and audit.

### Trace Boundaries

A workflow execution can last weeks. A single OTEL trace spanning that duration would be impractical to query or display. Instead:

| Concept | OTEL role | Lifetime |
|---|---|---|
| **User turn** | One trace (root span: `user_turn`) | Seconds to minutes — one WebSocket message through to response |
| **WebSocket session** | Attribute (`session_id`) on every span | Minutes to hours — one browser connection |
| **Workflow execution** | Attribute (`workflow_id`) on every span | Minutes to weeks — one Temporal workflow run |

Traces are short and queryable. Sessions and workflow IDs are attributes for cross-turn correlation ("show all turns for workflow X" or "all turns in session Y").

### How OTEL Integrates with Temporal

Temporal's Python SDK provides `TracingInterceptor` (`temporalio.contrib.opentelemetry`), which plugs into both `Client.connect(interceptors=[...])` and `Worker(interceptors=[...])`. It works at two levels:

* **Client side** (chat/agent process): When the agent's tool closures call `start_workflow`, `execute_update`, or `query`, the interceptor injects the current OTEL trace context into Temporal's gRPC headers as W3C `traceparent` metadata.
* **Worker side** (worker process): When the worker picks up a workflow task or activity, the interceptor extracts the propagated trace context from those headers and creates child spans. This means a span started in the agent process (e.g. `tool.submit_input`) becomes the parent of spans in the worker process (e.g. `HandleUpdate:submit_input`, `interpreter.InputState`).

This propagation happens automatically — no manual context passing is required. The two processes can run on different machines and the traces still link together via shared `trace_id`.

### Provider Setup Per Process

Each OS process owns its own `TracerProvider`:

* **Chat/agent process** (`chat.py:main()`): Creates a standard `TracerProvider` via `create_agent_provider()`. Attaches a `SessionSpanProcessor` (stamps `session_id` on all spans) and exporter(s). Sets it as the global provider. The `WorkflowAgent`'s Temporal client uses `TracingInterceptor` to propagate context on tool calls.
* **Worker process** (`worker.py:main()`): Creates a `ReplaySafeTracerProvider` via `create_worker_provider()`. This wraps a standard provider with Temporal's replay-safety logic: when the worker replays workflow history (which re-executes interpreter code deterministically), the provider suppresses span creation to prevent duplicate spans. The worker uses a `_FilteredTracingInterceptor` that extends `TracingInterceptor` to skip span creation for query handling — queries are high-frequency polling operations that would otherwise dominate the trace output.

### Span Instrumentation

**Chat/agent process:**

| Span name | Created in | Attributes |
|---|---|---|
| `user_turn` | `chat.py` WebSocket handler | `session_id`, `workflow_id`, `user_message_preview` |
| `agent.respond` | `agent.py` | `prompt_length`, `has_workflow_state` |
| `tool.start_workflow` | `agent.py` tool closure | `workflow_id` |
| `tool.submit_input` | `agent.py` tool closure | `workflow_id`, `token` |
| `tool.get_workflow_state` | `agent.py` tool closure | `workflow_id` |
| `tool.list_active_workflows` | `agent.py` tool closure | — |
| `tool.get_workflow_definition` | `agent.py` tool closure | `workflow_id` |
| `StartWorkflow:*`, `StartWorkflowUpdate:*` | Auto — `TracingInterceptor` | Temporal metadata |

**Worker process:**

| Span name | Created in | Attributes |
|---|---|---|
| `interpreter.InputState` | `interpreter.py` | `state_id`, `process_id`, `step`, `prompt`, `schema_kind`, `token`, `outcome`, `prompt_resolved`, `timeout_seconds`, `options_count` |
| `interpreter.CallState` | `interpreter.py` | `state_id`, `process_id`, `step`, `service`, `http.method`, `http.url`, `assign_target`, `outcome`, `captured_keys`, `error_message` |
| `interpreter.OutputState` | `interpreter.py` | `state_id`, `process_id`, `step`, `channel`, `message`, `notification_template`, `notification_outcome` |
| `RunActivity:http_call` | Auto — `TracingInterceptor` | `workflow_id`, `service`, `http.method`, `http.url`, `http.status_code`, `idempotency_key` |
| `RunWorkflow:*`, `HandleUpdate:*`, `ValidateUpdate:*` | Auto — `TracingInterceptor` | Temporal metadata |

Only `InputState`, `OutputState`, and `CallState` have manual spans — the remaining state types (`ChoiceState`, `AssignState`, `InvokeState`, `WaitState`, `EndState`) are cheap internal bookkeeping and are not instrumented.

### Polling Isolation

The background polling loop in `chat.py` (`stream_background_events`) queries Temporal every 500ms for transcript and awaiting-input state. To prevent this from generating hundreds of trace spans per minute, the polling loop uses a separate Temporal client (`_get_polling_client()`) that has no `TracingInterceptor`. Only the agent's tool closures — which execute during user turns — use the traced client. On the worker side, the `_FilteredTracingInterceptor` suppresses `HandleQuery` spans for the same reason.

### Trace Tree for a Single Turn

```
user_turn (chat.py)
│   session_id, workflow_id, user_message_preview
│
├── agent.respond (agent.py)
│   │
│   └── tool.submit_input (agent.py)
│       │
│       └── StartWorkflowUpdate:submit_input (TracingInterceptor, client side)
│           │
│           └── HandleUpdate:submit_input (TracingInterceptor, worker side)
│               │
│               ├── interpreter.InputState (interpreter.py)
│               │
│               ├── interpreter.CallState (interpreter.py)
│               │   │
│               │   └── RunActivity:http_call (TracingInterceptor, worker side)
│               │
│               └── interpreter.OutputState (interpreter.py)
```

### S3 Export Pipeline

Spans flow through the OTEL pipeline as follows:

1. Application code creates spans via `tracer.start_as_current_span()` or the `TracingInterceptor` creates them automatically.
2. The `SessionSpanProcessor` (chat process only) stamps `session_id` on each span as it starts.
3. Completed spans are queued in a `BatchSpanProcessor`, which flushes to the `S3SpanExporter` every 30 seconds (or on process shutdown).
4. The `S3SpanExporter` serializes each span as a JSON object (trace ID, span ID, name, timestamps, attributes, status) and accumulates them in memory.
5. On flush, the exporter writes the batch as a single JSONL object to S3 with a Hive-partitioned key:

```
{prefix}/year={y}/month={m}/day={d}/hour={h}/trace-{timestamp}.jsonl
```

The S3 bucket name is resolved from AWS Systems Manager Parameter Store (`/durable_poc/temp_trace_bucket`), with `OTEL_EXPORT_S3_BUCKET` as an environment variable override. The `FileSpanExporter` remains available for local development via `OTEL_EXPORT_FILE`.

---

## Test Architecture

| Test file | Scope | Dependencies |
|---|---|---|
| `test_pure.py` | `paths.py` and `predicates.py` — pure functions | None |
| `test_workflow.py` | Full interpreter execution and OTEL trace propagation against local Temporal dev server | `temporal` CLI binary |
| `test_agent_tools.py` | Tool functions with `FakeTemporalClient` and `httpx.MockTransport` | None |
| `test_agent.py` | `WorkflowAgent` composition, session state updates, contextual prompt building | None |
| `test_chat.py` | FastAPI WebSocket endpoints, message rendering, option generation | None |
| `test_tracing.py` | OTEL span creation, parent-child relationships, session stamping, activity enrichment | None |

---

## Entry Points

| Command | Entry Point File | Description |
|---|---|---|
| `python -m src.worker` | `src/worker.py` | **Temporal Worker**: Connects to Temporal (`localhost:7233`) and polls task queue `sfsm-queue`. Must be running for any workflow execution. |
| `python -m chat` | `chat.py` | **FastAPI Web App & WebSocket UI**: Launches the web application on `http://localhost:7860`. Serves the GOV.UK frontend and manages real-time agent/workflow streaming. |
| `python -m src.demo` | `src/demo.py` | **Terminal CLI (Legacy)**: Interactive terminal CLI driving workflows directly via raw Temporal queries/updates without the agent layer. |

```
