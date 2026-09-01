# Durable FSM Workflow Executor

A deterministic, durable Finite State Machine (FSM) executor built on the Temporal Python SDK paired with a real-time, GOV.UK-styled conversational interface and split-screen execution trace sidebar.

This project allows complex, long-running, asynchronous business processes to be defined entirely in JSON. The Python workflow executor interprets these definitions dynamically without requiring workflow-specific code. It handles human-in-the-loop interactions, branching logic, sub-processes, durable timers, and external HTTP integrations natively.

The agent layer uses AWS Bedrock (Claude) and the Strands framework purely as a silent NLU intent parser—converting user natural language into structured API calls—while the web UI directly renders transcript outputs, interactive input schemas, and real-time execution trace events straight from Temporal query snapshots.

## Key Features

* **Zero-Code Workflows**: Define states, transitions, HTTP calls, and polling loops entirely in JSON definitions (`SFSMDefinition`).
* **Strict Determinism**: All predicates and path resolutions are evaluated using structural recursion without string `eval()`, `exec()`, or unsafe expression engines, ensuring deterministic replay inside the Temporal sandbox.
* **Dual-Path Web Architecture**: Decouples LLM processing from UI display. The LLM handles intent parsing and tool invocation, while a background WebSockets stream renders transcript entries (`OutputState`) and interactive prompts (`InputState`) straight from Temporal.
* **Real-Time Event Trace Sidebar**: Split-screen execution sidebar displaying granular, real-time trace badges across four distinct event channels: `USER`, `AGENT` (tool selection), `ENGINE` (FSM transitions and HTTP dispatches), and `SYSTEM` (schema option renders).
* **Synchronous Input Validation**: Human inputs are submitted via Temporal Updates (not Signals), allowing the workflow to synchronously validate payloads against schema kinds or regex patterns and reject stale or duplicate tokens immediately.
* **Configurable Service Routing & Idempotency**: Environment-driven activity routing table (`SERVICE_ENV_MAP`) that validates target endpoints and automatically forwards interpolated `Idempotency-Key` headers to external APIs.
* **Sub-process Stack Frames**: Sub-processes execute as stack frames (`StackFrame`) within a single Temporal workflow context (rather than Child Workflows), supporting return mappings while keeping state serializable for Continue-As-New.
* **Activity Boundaries**: HTTP payloads are projected inside activities. Large response bodies never cross the workflow boundary, preventing history bloat.
* **UI Enhancements**: Dynamic button generation for selection schemas, timeout warning badge displays, terminal completion cards, and an active workflow resume dropdown picker.

## Project Structure

```text
durable_poc/
├── agent/
│   ├── __init__.py
│   ├── agent.py         # Strands agent composition & tool trace callbacks
│   ├── chat.py          # FastAPI Web Server, WebSockets UI & Split-Screen Trace
│   ├── tools.py         # Tool functions bridging agent to Temporal & Server
│   └── prompts/
│       └── system.txt   # Silent NLU system prompt with execution constraints
├── src/
│   ├── model.py         # Pydantic models enforcing the JSON definition schema
│   ├── paths.py         # Dot-path resolution, string interpolation & ISO durations
│   ├── predicates.py    # Pure, deterministic condition evaluator
│   ├── context.py       # Dataclasses for interpreter state, frames & transcripts
│   ├── interpreter.py   # Core Temporal Workflow loop, event yielding & sub-process stack
│   ├── activities.py    # Temporal activities (Configured HTTP requests & idempotency)
│   ├── errors.py        # Error taxonomy (Retryable, Validation, Definition)
│   ├── worker.py        # Temporal worker bootstrap
│   └── demo.py          # Interactive terminal CLI frontend (legacy)
├── tests/
│   ├── test_agent.py        # Agent composition and session state tests
│   ├── test_agent_tools.py  # Tool function unit tests
│   ├── test_chat.py         # FastAPI WebSocket interface & trace tests
│   ├── test_pure.py         # Unit tests for paths and predicates
│   └── test_workflow.py     # Integration tests using local Temporal dev server
└── dvla_coa_adv_schema.json # DVLA Change of Address FSM Definition
```

## Prerequisites

* **Python 3.14+** and [uv](https://docs.astral.sh/uv/) installed
* **Temporal CLI** installed (`brew install temporal`)

Install dependencies:

```bash
just build
```

Run the tests:

```bash
just test-poc
```

The test suite validates pure Python logic (path resolution, predicates), Temporal workflow loops (using a local dev server), agent tool functions, and the FastAPI WebSocket interface.

---

## Running the Agentic Chat Interface

The project includes a conversational AI agent that guides users through workflows using natural language. The agent uses Claude via AWS Bedrock and maintains workflow state using the HATEOAS pattern — each tool response is self-describing, carrying the continuation token and next expected input.

### Prerequisites

1. **Python 3.14+** and **uv** installed
2. **Temporal CLI** installed (`brew install temporal`)
3. **AWS credentials** with `bedrock:InvokeModel` permission for Claude Sonnet in your target region
4. **Workflow server** running (serves workflow definitions)

### Required Credentials

The agent calls Claude via Amazon Bedrock. You need valid AWS credentials configured via any standard method (environment variables, `~/.aws/credentials`, SSO, etc.). Verify with:

```bash
aws sts get-caller-identity
```

The default model is `anthropic.claude-sonnet-4-6` in `eu-west-2`. Override with environment variables if needed:

```bash
export BEDROCK_MODEL_ID="anthropic.claude-sonnet-4-6"
export AWS_REGION="eu-west-2"
```

### Running the Demo

You need four terminal windows, all running from the repository root.

#### Terminal 1: Temporal Server

```bash
temporal server start-dev
```

Runs on `localhost:7233`. The Temporal UI is available at `http://localhost:8233`.

#### Terminal 2: Workflow Definition Server

The workflow server must be running on port 8080, serving workflow definitions at `GET /api/v1/workflows/{id}`.  The workflow server code is [here](https://github.com/govuk-once/spike-legibility-workflow-server). Clone it and follow the instructions to run it.

Verify it is responding:

```bash
curl http://localhost:8080/api/v1/workflows
```

#### Terminal 3: Temporal Worker

Starts the Python worker that executes the FSM interpreter and activities:

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.worker
```

The worker connects to Temporal on `localhost:7233` and listens on the `sfsm-queue` task queue.

#### Terminal 4: Web Agent Chat UI

Launch the WebSockets server and chat interface:

```bash
cd durable_poc
PYTHONPATH=. uv run python -m agent.chat
```

Open `http://localhost:7860` in your browser.

---

## Using the Chat Interface

Type a natural language message in the chat box to start a workflow:

> *"I need to change the address on my driving licence."*

The agent will:
1. Fetch the appropriate workflow definition from the server
2. Start a Temporal workflow execution
3. Stream prompts, options, and transcript outputs directly via WebSockets to the frontend, interpreting user responses into structured schema values behind the scenes.

To resume an active running workflow from a previous session, select it directly from the **Resume Active Session** dropdown at the top of the interface and click **Resume**.


The agent will query Temporal for running workflows and pick up where you left off.

---

## Configuration Reference

| Environment Variable | Default | Purpose |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server gRPC address |
| `WORKFLOW_SERVER_URL` | `http://localhost:8080` | Workflow definition server URL |
| `BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-6` | AWS Bedrock Claude model identifier |
| `AWS_REGION` | `eu-west-2` | AWS region for Bedrock |
| `DVLA_BASE` | `http://localhost:8000` | Target base URL for DVLA service activity calls |
| `POSTOFFICE_BASE` | `http://localhost:8000` | Target base URL for Post Office activity calls |

---

## Running the Terminal CLI Demo (Legacy)

The project also includes an interactive terminal demo (`demo.py`) that executes workflows without an AI agent. This requires the same Temporal server and worker, plus a stub backend server.

#### Terminal 1: Temporal Server

```bash
temporal server start-dev
```

#### Terminal 2: Backend Stub Server

```bash
python stub_server.py
```
*(Runs on `http://localhost:8000`)*

#### Terminal 3: Temporal Worker

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.worker
```

#### Terminal 4: The Interactive CLI

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.demo
```

Follow the prompts in this terminal to step through the state machine.

---

## State Types Reference

* **`input`**: Suspends the workflow and exposes an awaited schema. Resumes when a matching payload is submitted via Update. Supports timeouts.
* **`choice`**: Evaluates a list of rules (using operators like `eq`, `lt`, `is_true`, `not_empty`) and branches execution.
* **`assign`**: Mutates the current stack frame's variable context (including `now_plus` and integer `add`).
* **`call`**: Dispatches `http_call` activity with service validation, capture projections, error catches, and idempotency headers.
* **`invoke`**: Pushes a sub-process stack frame onto the workflow call stack, binding inputs and catch routes.
* **`output`**: Emits internal transcript messages or fires external notification activities.
* **`wait`**: Durably sleeps the workflow for an ISO 8601 duration string (e.g., `PT5M`).
* **`end`**: Terminates the current process frame with a status and return payload.