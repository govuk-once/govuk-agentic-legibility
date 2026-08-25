# Architecture

## Overview

The `durable_poc` application is a two-layer system:

1. **Executor layer** (`src/`) — A deterministic, durable Finite State Machine interpreter running inside Temporal. It accepts a JSON workflow definition and executes it step by step, suspending at human-in-the-loop input states and resuming when structured input is submitted via Temporal Updates.

2. **Agent layer** (`agent/`) — A conversational front-end powered by an LLM (Claude via AWS Bedrock) using the Strands Agents framework. It translates between natural language and the structured inputs the executor expects, while Temporal remains the single source of truth for workflow state.

The core research question: **can an LLM agent faithfully execute a strictly-defined process while providing natural language UX — without hallucinating steps, skipping states, or inventing options outside the definition?** Temporal is the integrity guardrail; the agent can only advance the workflow by submitting valid tokens through the executor's update validator.

```
┌──────────────────────────────────────────────────────────┐
│                  User (Browser)                           │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP (Gradio WebSocket)
┌────────────────────────▼─────────────────────────────────┐
│  agent/chat.py — Gradio Blocks UI                        │
│    Routes messages to WorkflowAgent.respond()            │
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

Pydantic models that parse and validate the JSON workflow definition. The top-level model is `SFSMDefinition`, which contains:

- `schema_`: Schema version identifier (e.g. `"sfsm/0.2"`)
- `id`: Workflow logical identifier (e.g. `"dvla.change_of_address"`)
- `version`: Semantic version string
- `entry`: Name of the starting process
- `executor`: Configuration for Temporal execution (ID template, timeouts, continue-as-new policy)
- `processes`: Map of process names to `Process` objects

Each `Process` has a `start` state, initial `vars`, and a `states` map. States are discriminated unions:

| State type | Purpose |
|---|---|
| `InputState` | Suspend workflow, expose a schema for human input |
| `OutputState` | Emit a transcript message or fire a notification activity |
| `CallState` | Execute an HTTP call via an activity |
| `ChoiceState` | Evaluate predicate rules and branch |
| `AssignState` | Mutate the frame's variable context |
| `InvokeState` | Push a sub-process frame onto the stack |
| `WaitState` | Durably sleep for an ISO 8601 duration |
| `EndState` | Pop the current frame, optionally returning data to the parent |

### `src/context.py` — Runtime State

Dataclasses representing the interpreter's mutable state:

- **`InterpreterState`** — The full execution state: a stack of `StackFrame`s, a transcript, a step counter, and an environment dict. This entire object is serializable for Temporal's continue-as-new.
- **`StackFrame`** — One frame on the call stack: `process_id`, `state_id`, and a `vars` dict (the frame's local variable scope).
- **`TranscriptEntry`** — A timestamped message emitted by `OutputState` nodes.
- **`AwaitingInput`** — Published via query when the workflow is waiting for human input: contains `token`, `prompt`, `schema`, optional resolved `options`, and optional `timeout_seconds`.
- **`InputSubmission`** — The payload submitted via Temporal Update: a `token` (for idempotency/ordering) and an arbitrary `value`.

### `src/interpreter.py` — The Workflow

`SFSMInterpreter` is a `@workflow.defn` class. Its `run` method is the deterministic execution loop:

1. Validates the incoming definition dict against `SFSMDefinition`
2. Initialises the stack (or resumes from a provided `InterpreterState` after continue-as-new)
3. Loops while frames remain on the stack, dispatching on the current state's type
4. For `InputState`: publishes `AwaitingInput` via query, then blocks on `workflow.wait_condition` until the `submit_input` update fires (or a timeout expires)
5. For `CallState`/`OutputState`: delegates to Temporal activities
6. For `EndState`: pops the frame; if it was the last frame, returns the final result

Key Temporal primitives used:

- **Update** (`submit_input`): Receives user input synchronously, allowing the workflow to validate and reject in the same round-trip. A `_validate_input` validator checks token freshness and schema conformance before the update handler runs.
- **Query** (`awaiting`, `transcript`): Read-only access to current state without advancing the workflow. Used by the agent to poll what the workflow needs next.
- **Continue-as-new**: When Temporal suggests it (history size), the interpreter serialises its full state and restarts, keeping history bounded.

### `src/paths.py` — Path Resolution

Pure utility functions for the interpreter's expression language:

- `resolve_path(context, "a.b.c")` — Dot-path traversal into nested dicts/lists
- `set_path(context, "a.b", val)` — Dot-path assignment (creates intermediate dicts)
- `interpolate(template, context)` — Replaces `{{path.to.var}}` placeholders in strings
- `resolve_dict(data, context)` — Recursively resolves `{"$": "path"}` references in nested structures
- `parse_duration("PT5M")` — ISO 8601 duration string to `timedelta`

### `src/predicates.py` — Condition Evaluator

Pure function `evaluate(condition, context)` implementing the workflow's branching operators: `eq`, `lt`, `gt`, `is_true`, `is_false`, `not_empty`, `and`, `or`, `not`, `before_now`, `contains`. All evaluation is structural recursion against the context dict — no `eval()` or expression parsing.

### `src/activities.py` — External Integrations

Temporal activities that run outside the deterministic sandbox:

- **`http_call(CallParams)`** — Makes an HTTP request and returns a projected subset of the response (status, headers, body fields) as defined by the `capture` specification. Retryable on 5xx/429.
- **`notify(NotifyParams)`** — Sends a notification via a named channel (currently logs; production would dispatch to email/SMS/etc).

### `src/errors.py` — Error Taxonomy

- `DefinitionError` — Invalid schema or missing state references (halts the workflow)
- `ApplicationError` — Base for activity errors that cross into workflow routing
- `RetryableHttpError` — 5xx/429/timeout (Temporal retries automatically)
- `ValidationError` — Non-retryable constraint violation (workflow catches and routes)
- `InputValidationError` — Raised synchronously in the update validator; surfaces to the caller immediately

### `src/worker.py` — Worker Bootstrap

Entry point: `python -m src.worker`. Connects to Temporal, registers `SFSMInterpreter` and the activities, then runs the worker polling on the `sfsm-queue` task queue.

### `src/client.py` — Client Helpers

Convenience functions wrapping the Temporal Client SDK for starting workflows, submitting input, and querying state. Used by the legacy terminal demo.

### `src/demo.py` — Terminal CLI (Legacy)

An interactive terminal loop that drives a workflow execution directly via Temporal queries and updates. This was the original front-end before the agent layer; it requires the user to enter raw structured values.

---

## Agent Layer (`agent/`)

### `agent/tools.py` — Tool Functions

Pure async functions that bridge between the agent and external systems. Each function takes explicit dependencies (http_client, temporal_client) as keyword arguments, making them testable with fakes:

| Function | Purpose | External system |
|---|---|---|
| `get_workflow_definition(workflow_id, http_client, base_url)` | Fetch a workflow definition by numeric ID | Workflow server (HTTP) |
| `start_workflow(workflow_id, http_client, base_url, temporal_client, task_queue)` | Fetch definition then start it on Temporal | Both |
| `list_active_workflows(temporal_client)` | List running SFSMInterpreter executions | Temporal (gRPC) |
| `get_workflow_state(workflow_id, temporal_client)` | Query awaiting + transcript | Temporal (gRPC) |
| `submit_input(workflow_id, token, value, temporal_client)` | Submit input via Update, return new state | Temporal (gRPC) |

`start_workflow` deliberately accepts only the numeric `workflow_id` (not a full definition). It fetches the definition internally, preventing the LLM from fabricating partial or hallucinated workflow JSON.

`submit_input` follows the HATEOAS pattern: after submitting, it immediately queries and returns the new workflow state, so the agent always has the authoritative next step without a separate query call.

### `agent/agent.py` — WorkflowAgent

The composition layer that wires the Strands agent to the tool functions.

**Construction:**

```python
WorkflowAgent(
    workflow_server_url="http://localhost:8080",
    model_id="anthropic.claude-sonnet-4-6",
    region_name="eu-west-2",
    temporal_address="localhost:7233",
    task_queue="sfsm-queue",
)
```

The agent exists independently of any live connections. Temporal and HTTP clients are `None` at construction time.

**Lazy connection pattern:**

`_get_temporal_client()` and `_get_http_client()` connect on first use. This ensures the gRPC channel binds to whatever event loop is active at call time — critical because Gradio's uvicorn loop differs from the loop that would exist at module import time.

**Tool closures:**

`_build_tools()` creates `@tool`-decorated async closures that capture `owner` (a reference to the agent instance). Each closure:
1. Acquires the appropriate client via `owner._get_temporal_client()` / `owner._get_http_client()`
2. For `submit_input`: coerces the `value` argument via `_coerce_value()` (see below)
3. Delegates to the corresponding function in `agent/tools.py`
4. Calls `owner._update_session_state()` to keep the HATEOAS continuation state current

**Value coercion (`_coerce_value`):**

LLMs emit tool arguments as JSON, but don't reliably produce the correct JSON type — e.g. passing `"Yes"` (string) when the schema expects a boolean `true`. The `_coerce_value` function inspects the `kind` field from the current awaiting schema in session state and coerces the value:

- `kind: "boolean"` — string → `True`/`False` (matches against a set of truthy words)
- `kind: "string"` — non-string → `str(value)`
- `kind: "object"` — JSON string → parsed dict

This is a defensive fallback. The primary mechanism is the system prompt, which explicitly instructs the LLM to pass correctly-typed values. The coercion catches cases where the LLM disregards the instruction — without it, Temporal's update validator would reject the submission and the user would see an opaque error.

**Session state:**

`_session_state` is a dict with `workflow_id` and `awaiting` (the current `AwaitingInput` or `None`). It is updated by every state-changing tool call. The chat layer reads it before each turn and passes it as context to `build_contextual_prompt()`.

**`build_contextual_prompt(user_message, context)`:**

When context exists, the user's message is augmented with the current workflow state (active workflow ID, pending token, prompt text, and input schema). This eliminates reliance on conversation memory for state tracking — the agent always has the authoritative state from Temporal.

**`respond(user_message, context)`:**

Builds the contextual prompt and calls `self._agent.invoke_async(prompt)`. Returns the agent's text response as a string.

### `agent/prompts/system.txt` — System Prompt

The system prompt establishes the agent's behavioural contract:

1. **Role**: Government service workflow assistant
2. **Integrity rules**: Never skip, invent, or reorder steps. Only present options the schema defines. If a submission is rejected, inform the user.
3. **Type discipline**: Explicit instruction that `value` passed to `submit_input` must be the correct JSON type (`true`/`false` for booleans, strings for strings, objects for objects) — not a string representation. Includes concrete examples of correct tool calls for each schema kind.
4. **NLU guidance**: How to interpret natural language into each schema type (boolean, string with pattern, select_one, object, file_ref)
5. **Tool usage**: When to use each tool (start vs resume, query vs submit)
6. **Communication style**: Concise, one step at a time, don't dump the full definition

### `agent/chat.py` — Gradio UI

**`create_chat_fn(agent)`** — Returns an async function `(message, history, state) -> (response, state)` that:
1. Reads session state (from Gradio's `gr.State` or the agent's own `session_state`)
2. Calls `agent.respond(message, context=state)`
3. Returns the response and the updated session state

**`create_app(agent)`** — Builds a `gr.Blocks` layout with a Chatbot, State, and Textbox. The `msg.submit` event wires through the chat function, appending messages to history and threading state.

**`main()`** — The entry point (`python -m agent.chat`). Creates a `WorkflowAgent` from environment variables, builds the Gradio app, and launches it. No async setup required — the agent connects to Temporal lazily when the first user message triggers a tool call.

---

## Data Flow: A Complete Turn

1. User types "I need to change my address" in the Gradio UI
2. `chat.py` calls `agent.respond("I need to change my address", context=None)`
3. `build_contextual_prompt` returns the raw message (no context yet)
4. Strands agent receives the message, decides to call `start_workflow(workflow_id=1)`
5. The tool closure calls `_get_temporal_client()` → connects lazily to Temporal
6. `tools.start_workflow` fetches the definition from the workflow server, then calls `temporal_client.start_workflow("SFSMInterpreter", arg=definition, ...)`
7. The Temporal worker picks up the workflow, enters the first `InputState`, publishes `AwaitingInput` via query
8. The tool closure queries state and updates `session_state` with the workflow_id and awaiting info
9. The agent sees the returned state (prompt: "Do you confirm you want to change your address?", schema: boolean, token: tkn_1) and formulates a natural language response
10. The response flows back through Gradio to the user

On the next turn:
1. User types "yes"
2. `chat.py` passes `session_state` (containing workflow_id, token, awaiting) as context
3. `build_contextual_prompt` augments the message with state context
4. The agent calls `submit_input(workflow_id="sfsm-dvla.change_of_address-0.2.0", token="tkn_1", value="Yes")` — note: the LLM may pass a string
5. `_coerce_value` sees schema kind is `"boolean"`, coerces `"Yes"` → `True`
6. Temporal's update validator checks the token matches and type is correct → accepts
7. The workflow advances to the next state
8. `submit_input` queries and returns the new state (next prompt, next token)
9. The agent presents the next step conversationally

---

## Key Design Decisions

### Temporal Updates (not Signals) for input

Updates are synchronous: the submit call blocks until the workflow validates and accepts (or rejects). This means the agent gets immediate feedback on invalid submissions — token mismatch, wrong type, pattern failure — and can inform the user in the same turn.

### HATEOAS continuation state

Each tool response is self-describing: it carries the next expected token, prompt, and schema. The agent never needs to "remember" what step it's on — the state is always derived from Temporal's query response. This makes the system resilient to conversation context loss and prevents the LLM from drifting out of sync with the actual workflow state.

### Agent independence from Temporal at construction

The `WorkflowAgent` takes only configuration strings (addresses, model IDs) at construction. Live connections are deferred until the first tool call. This solves the event loop binding problem: Gradio runs its own uvicorn asyncio loop, which differs from any loop that exists at import/construction time. By connecting lazily inside a tool call, the gRPC channel binds to Gradio's loop.

### Tool design prevents hallucination vectors

- `start_workflow` accepts only a numeric ID and fetches the definition internally — the LLM cannot fabricate workflow content
- `submit_input` requires a token that must match the workflow's current expectation — stale or invented tokens are rejected by the validator
- The system prompt forbids presenting options not in the schema, but even if the LLM hallucinates an option, Temporal will reject the submission
- `_coerce_value` bridges the type-system gap between LLM output (which may produce `"Yes"` instead of `true`) and the strict Temporal validator, preventing opaque errors that would break the conversation flow

### Sub-process stack (not child workflows)

The interpreter uses a frame stack within a single Temporal workflow execution. This keeps the entire state serializable for continue-as-new and avoids the complexity of child workflow signalling and cancellation.

---

## Test Architecture

| Test file | Scope | Dependencies |
|---|---|---|
| `test_pure.py` | `paths.py` and `predicates.py` — pure functions | None |
| `test_workflow.py` | Full interpreter execution against a local Temporal dev server | `temporal` CLI binary |
| `test_agent_tools.py` | Tool functions with `FakeTemporalClient` and `httpx.MockTransport` | None |
| `test_agent.py` | `WorkflowAgent` composition, session state updates, contextual prompt building | None |
| `test_chat.py` | Gradio chat function delegation and app construction | None |

The fake objects (`FakeTemporalClient`, `FakeWorkflowHandle`, `FakeWorkflowListIterator`) implement the minimal interface the tools expect. `httpx.MockTransport` exercises the real httpx async client code path while controlling responses.

---

## Entry Points

| Command | What it starts |
|---|---|
| `python -m src.worker` | Temporal worker (must be running for any workflow execution) |
| `python -m agent.chat` | Gradio chat UI on port 7860 |
| `python -m src.demo` | Legacy terminal CLI |
