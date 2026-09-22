# Durable FSM Workflow Executor

A deterministic, durable Finite State Machine (FSM) executor built on the Temporal Python SDK paired with a real-time, GOV.UK-styled conversational interface and split-screen execution trace sidebar.

This project allows complex, long-running, asynchronous business processes to be defined entirely in JSON. The Python workflow executor interprets these definitions dynamically without requiring workflow-specific code. It handles human-in-the-loop interactions, branching logic, sub-processes, durable timers, and external HTTP integrations natively.

The agent layer uses AWS Bedrock (Claude) and the Strands framework purely as a silent NLU intent parser—converting user natural language into structured API calls—while the web UI directly renders transcript outputs, interactive input schemas, and real-time execution trace events straight from Temporal query snapshots.

## Key Features

* **Zero-Code Workflows**: Define states, transitions, HTTP calls, and polling loops entirely in JSON definitions (`SFSMDefinition`).
* **Strict Determinism**: All predicates and path resolutions are evaluated using structural recursion without string `eval()`, `exec()`, or unsafe expression engines, ensuring deterministic replay inside the Temporal sandbox.
* **Dual-Path Web Architecture**: Decouples LLM processing from UI display. The LLM handles intent parsing and tool invocation, while a background WebSockets stream renders transcript entries (`OutputState`) and interactive prompts (`InputState`) straight from Temporal.
* **Real-Time Event Trace Sidebar**: Split-screen execution sidebar displaying granular, real-time trace badges across four distinct event channels: `USER`, `AGENT` (tool selection), `ENGINE` (FSM transitions and HTTP dispatches), and `SYSTEM` (schema option renders).
* **Synchronous Input Validation**: Human inputs are submitted via Temporal Updates (not Signals), allowing the workflow to synchronously validate payloads against schema kinds, regex patterns, or `file_ref` metadata and reject stale or duplicate tokens immediately.
* **Configurable Service Routing & Idempotency**: Environment-driven activity routing table (`SERVICE_ENV_MAP`) that validates target endpoints and automatically forwards interpolated `Idempotency-Key` headers to external APIs.
* **Sub-process Stack Frames**: Sub-processes execute as stack frames (`StackFrame`) within a single Temporal workflow context (rather than Child Workflows), supporting return mappings while keeping state serializable for Continue-As-New.
* **Activity Boundaries**: HTTP payloads are projected inside activities. Large response bodies never cross the workflow boundary, preventing history bloat.
* **UI Enhancements**: Dynamic button generation for selection schemas, file upload attachment bridge, timeout warning badge displays, terminal completion cards, and an active workflow resume dropdown picker.

## Project Structure

```text
durable_poc/
├── agent/
│   ├── __init__.py
│   ├── agent.py         # Strands agent composition, value coercion & trace callbacks
│   ├── chat.py          # FastAPI Web Server, WebSockets UI & Split-Screen Trace
│   ├── tools.py         # Tool functions bridging agent to Temporal & Server
│   └── prompts/
│       └── system.txt   # Silent NLU system prompt with execution constraints
├── src/
│   ├── actions.py       # Date arithmetic math helpers
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
├── dvla_coa_adv_schema.json # DVLA Change of Address FSM Definition
└── dwp_ma1_schema.json      # DWP Maternity Allowance (MA1) FSM Definition
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

The test suite validates pure Python logic (path resolution, predicates), Temporal workflow loops (using a local dev server), agent tool functions, coercion logic, and the FastAPI WebSocket interface.

---

# Deployment to AWS

The project can be deployed to AWS using AWS CDK. The deployment provisions the infrastructure required to run the Durable FSM Executor stack, including:

- EC2 host for the chat application and Temporal services
- Networking resources (VPC, Security Groups)
- IAM roles and permissions
- Public DNS endpoint
- Environment configuration for Bedrock access
- Systemd services for:
  - Temporal Server
  - Temporal Worker
  - Chat Interface

To deploy after making code changes, from the repository root:

```bash
cd infrastructure
cdk deploy DurablePocStack
```

After deployment, view CloudFormation Outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name DurablePocStack
```

After deployment completes, you may connect to the EC2 instance and check the startup logs:

```text
sudo less /var/log/cloud-init-output.log
```

you may also check that the application services are running:

```text
sudo systemctl status temporal
sudo systemctl status temporal-worker
sudo systemctl status durable-chat
```

---

## Running the Agentic Chat Interface (AWS Hosted Environment)

The Durable FSM Workflow Executor has been deployed to AWS for shared testing and demonstration purposes. The following services are hosted in AWS and can be consumed directly without running them locally:

- Workflow Definition Server
- Backend Stub Services
- Temporal Worker
- Temporal Server
- Chat Interface

The deployed chat interface can be accessed through the public DNS endpoint provisioned by the AWS CDK deployment:

```text
http://ec2-3-8-139-240.eu-west-2.compute.amazonaws.com:7860
```

Note: The instructions in the Running the Agentic Chat Interface section below are intended for local development only. If you are using the AWS-hosted deployment, you do not need to start Temporal, the worker, the Workflow Server, or the Stub Server locally.

---

## Running the Agentic Chat Interface (Local Development Only)

The following instructions are intended for contributors developing the project locally. For most users, a fully deployed version of the platform is available in AWS and can be accessed through its public DNS endpoint without starting any services locally.

When running locally, the following default ports are used:

- Temporal Server: `7233`
- Temporal UI: `8233`
- Stub Server: `8000`
- Workflow Server: `8080`
- Agent Chat UI: `7860`

### Running the Demo

The demo requires multiple terminal sessions running simultaneously.

#### Terminal 1: Temporal Server

Start the Temporal development server:

```bash
temporal server start-dev
```

The Temporal server will run on:

```text
localhost:7233
```

The Temporal UI will be available at:

```text
http://localhost:8233
```

---

####  Terminal 2: Temporal Worker

Starts the Python worker that executes the FSM interpreter and activities:

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.worker
```

The worker connects to Temporal at:

```text
localhost:7233
```

and listens on the:

```text
sfsm-queue
```

task queue.

---

#### Terminal 3: Backend Stub Server

The worker executes HTTP activities that call backend services. The stub server is currently deployed to AWS ECS under the `govuk-once-ailegibility-development` account. Therefore, the service endpoint environment variables must be available in the same terminal session where the Temporal worker is running.

Configure the service endpoints:

```bash
export DVLA_BASE='http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com'
export POSTOFFICE_BASE='http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com'
export HMRC_BASE='http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com'
export DWP_BASE='http://DvlaMo-MockS-FSSFl9ywaoQu-392957609.eu-west-2.elb.amazonaws.com'
```

Alternatively, the stub server can be run locally.

Repository:

```text
https://github.com/govuk-once/stub-domain-legibility
```

Follow the repository instructions to start the server locally.

Default local URL:

```text
http://localhost:8000
```
---

#### Terminal 4: Workflow Definition Server

The chat application retrieves workflow definitions from the Workflow Server. The Workflow Server is currently deployed to AWS ECS under the `govuk-once-ailegibility-development` account.

Before starting the chat UI, configure the Workflow Server endpoint:

```bash
export WORKFLOW_SERVER_URL='http://Workfl-Workf-CwPhUxgpA91a-749675269.eu-west-2.elb.amazonaws.com'
```

Alternatively, the Workflow Server can be run locally.

Repository:

```text
https://github.com/govuk-once/spike-legibility-workflow-server
```

Follow the repository instructions to start the server locally.

Default local URL:

```text
http://localhost:8080
```

---

#### Terminal 5: Agent Chat UI

Start the WebSocket server and chat interface:

```bash
cd durable_poc
PYTHONPATH=. uv run python -m agent.chat
```

Open the chat interface in your browser:

```text
http://localhost:7860
```

---

## Using the Chat Interface

Type a natural language message in the chat box to start a workflow:

Example:

> I need to change the address on my driving licence.

The agent will:
1. Fetch the appropriate workflow definition from the server
2. Start a Temporal workflow execution
3. Stream prompts, options, and transcript outputs directly via WebSockets to the frontend, interpreting user responses into structured schema values behind the scenes.

To resume an active running workflow from a previous session, select it directly from the **Resume Active Session** dropdown at the top of the interface and click **Resume**.


The agent will query Temporal for running workflows and pick up where you left off.

---

# Running the Terminal CLI Demo (Legacy)

The project also includes a terminal-based demo (`demo.py`) that executes workflows without using the chat interface.

This requires the following services to be running (see instructions above):

- Temporal Server
- Temporal Worker
- Stub Server
- Workflow Server

### Terminal 5: Interactive CLI

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.demo
```

You can then interact with workflows directly through the terminal instead of the web-based chat interface. Follow the prompts in this terminal to step through the state machine.