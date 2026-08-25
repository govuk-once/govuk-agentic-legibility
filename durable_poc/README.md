# Durable FSM Workflow Executor
A deterministic, durable Finite State Machine (FSM) executor built on the Temporal Python SDK.

This project allows the user to define complex, long-running, asynchronous processes entirely in JSON. The Python workflow executor interprets these JSON definitions dynamically without requiring any workflow-specific code. It handles human-in-the-loop interactions, branching logic, sub-processes, durable timers, and external HTTP integrations natively.

## Key Features
- Zero-Code Workflows: Define states, transitions, HTTP calls, and polling loops entirely in a JSON schema.

- Strict Determinism: All predicates and path resolutions are evaluated using structural recursion. No eval(), exec(), or external expression engines are used, ensuring perfect replayability inside the Temporal sandbox.

- Synchronous Input Validation: Human inputs are submitted via Temporal Updates (not Signals), allowing the workflow to synchronously validate payloads against the schema and reject stale or duplicate tokens.

- Sub-process Stack: Sub-processes execute as frames within the same workflow context (rather than Child Workflows), keeping the entire interpreter state perfectly serializable for continue_as_new.

- Activity Boundaries: HTTP payloads are structurally projected inside the activity. Large or unneeded payloads never cross the workflow boundary, preventing workflow history bloat.

## Project Structure
```text
durable_poc/
├── agent/
│   ├── __init__.py
│   ├── agent.py         # Strands agent composition (WorkflowAgent class)
│   ├── chat.py          # Gradio chat UI entrypoint
│   ├── tools.py         # Tool functions bridging agent to Temporal
│   └── prompts/
│       └── system.txt   # Agent system prompt with integrity constraints
├── src/
│   ├── model.py         # Pydantic models enforcing the JSON definition schema
│   ├── paths.py         # Dot-path resolution and string interpolation
│   ├── predicates.py    # Pure, deterministic condition evaluator
│   ├── context.py       # Dataclasses for the interpreter state and frame stack
│   ├── interpreter.py   # The core Temporal Workflow loop
│   ├── activities.py    # Temporal activities (HTTP requests, notifications)
│   ├── errors.py        # Error taxonomy (Retryable, Validation, etc.)
│   ├── worker.py        # Temporal worker bootstrap
│   └── client.py        # Client helpers (start, query, update)
├── tests/
│   ├── test_agent.py        # Agent composition and session state tests
│   ├── test_agent_tools.py  # Tool function unit tests
│   ├── test_chat.py         # Gradio chat interface tests
│   ├── test_pure.py         # Unit tests for paths and predicates
│   └── test_workflow.py     # Integration tests using local Temporal server
├── stub_server.py       # FastAPI mock backend (Photo upload & DVLA polling)
└── demo.py              # Interactive terminal CLI frontend (legacy)
```

## Prerequisites

- Python 3.14+ and [uv](https://docs.astral.sh/uv/) installed
- Temporal CLI installed (`brew install temporal`)

Install dependencies:

```bash
just build
```

Run the tests:

```bash
just test-poc
```

The test suite validates the pure Python logic (path resolution, predicates), Temporal integration (using a local dev server), agent tool functions, and the chat interface wiring.

## Running the Agentic Chat Interface

The project includes a conversational AI agent that guides users through workflows using natural language. The agent uses Claude via AWS Bedrock and maintains workflow state using the HATEOAS pattern — each tool response is self-describing, carrying the continuation token and next expected input.

### Prerequisites

1. **Python 3.14+** and **uv** installed
2. **Temporal CLI** installed (`brew install temporal`)
3. **AWS credentials** with `bedrock:InvokeModel` permission for Claude Sonnet in your target region
4. **Workflow server** running (serves workflow definitions)

### Required credentials

The agent calls Claude via Amazon Bedrock. You need valid AWS credentials configured via any standard method (environment variables, `~/.aws/credentials`, SSO, etc.). Verify with:

```bash
aws sts get-caller-identity
```

The default model is `us.anthropic.claude-sonnet-4-20250514-v1:0` in `eu-west-2`. Override with environment variables if needed:

```bash
export BEDROCK_MODEL_ID="anthropic.claude-sonnet-4-6"
export AWS_REGION="eu-west-2"
```

### Running the demo

You need four terminal windows, all running from the repository root.

#### Terminal 1: Temporal Server

```bash
temporal server start-dev
```

Runs on `localhost:7233`. The Temporal UI is available at `http://localhost:8233`.

#### Terminal 2: Workflow Definition Server

The workflow server must be running on port 8080, serving workflow definitions at `GET /api/v1/workflows/{id}`. The workflow server code is [here](https://github.com/govuk-once/spike-legibility-workflow-server). Clone it and follow the instructions to run it.

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

#### Terminal 4: Gradio Chat UI

Launch the chat interface:

```bash
cd durable_poc
PYTHONPATH=. uv run python -m agent.chat
```

Open `http://localhost:7860` in your browser.

### Using the chat

Type a natural language message to start a workflow:

> "I need to change the address on my driving licence."

The agent will:
1. Fetch the appropriate workflow definition from the server
2. Start a Temporal workflow execution
3. Present each step conversationally, interpreting your responses into the structured values the workflow expects

To resume an existing workflow in a new session, say something like:

> "I need to check on my driving licence task."

The agent will query Temporal for running workflows and pick up where you left off.

### Configuration

| Environment variable | Default | Purpose |
|---------------------|---------|---------|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server address |
| `WORKFLOW_SERVER_URL` | `http://localhost:8080` | Workflow definition server |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Bedrock model identifier |
| `AWS_REGION` | `eu-west-2` | AWS region for Bedrock |

---

## Running the Terminal CLI Demo (legacy)

The project also includes an interactive terminal demo (demo.py) that executes workflows without an AI agent. This requires the same Temporal server and worker, plus a stub backend server.

#### Terminal 1: Temporal Server

```bash
temporal server start-dev
```

#### Terminal 2: Backend Stub Server

```bash
python stub_server.py
```
(Runs on http://localhost:8000)

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

### Available state types:

- `input`: Suspends the workflow and exposes an awaited schema. Resumes when a matching payload is submitted via Update. Supports timeouts.

- `choice`: Evaluates a list of rules (using operators like eq, lt, is_true, not_empty) and branches the workflow.

- `assign`: Mutates the current stack frame's variable context.

- `call`: Dispatches the http_call activity to make an external request. Maps external errors (4xx/5xx) appropriately and uses capture to project only specific fields into the workflow state.

- `invoke`: Pushes a new sub-process onto the stack. Returns data to the calling frame via assign and handles sub-process exceptions via catch.

- `output`: Emits internal transcript messages or fires external notification activities.

- `wait`: Durably sleeps the workflow for an ISO 8601 duration (e.g., PT5M).

- `end`: Terminates the current process frame with a status and return payload.