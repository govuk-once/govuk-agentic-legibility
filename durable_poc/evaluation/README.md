# Durable workflow evaluation

The durable PoC evaluation runner tests one real workflow interaction repeatedly
without replaying every earlier service step. Each test case is self-contained
under `durable_poc/evaluation/scenarios/` and combines:

- the semantic expectation (`scenario.yaml`);
- the user-visible conversation ending in the turn under test (`conversation.json`);
- a real captured SFSM interpreter stack frame (`checkpoint.json`).

The runner starts a fresh Temporal workflow from the captured checkpoint, seeds
the real `WorkflowAgent` with the preceding conversation, sends the final user
turn, converts the executor OTEL evidence to the shared common-trace vocabulary,
and scores that trace with the shared evaluator.

## File structure

```text
durable_poc/evaluation/
├── README.md
├── capture_checkpoint.py
├── checkpoint_runner.py
├── otel_common_trace.py
├── scenario_case.py
└── scenarios/
    └── maternity_allowance/
        ├── baby_not_born/
        │   ├── scenario.yaml
        │   ├── conversation.json
        │   └── checkpoint.json
        ├── date_stopped_work_natural_language/
        │   ├── scenario.yaml
        │   ├── conversation.json
        │   └── checkpoint.json
        ├── payment_frequency_fortnightly/
        │   ├── scenario.yaml
        │   ├── conversation.json
        │   └── checkpoint.json
        └── work_status_fixed_term_contract_ended/
            ├── scenario.yaml
            ├── conversation.json
            └── checkpoint.json
```

The filenames inside a case directory are conventions, not scenario
configuration. `scenario.yaml` therefore does not repeat paths or checkpoint
IDs.

For example:

```yaml
schema_version: "0.1"
id: "ma-work-status-fixed-term-contract-ended"
journey_id: "dwp.maternity_allowance_ma1_claim"

expected:
  submissions:
    prompt_reason_stopped_work:
      values:
        reason_stopped_work: "resigned_or_redundant"
```

`conversation.json` must have the same `id` and `journey_id` as the scenario.
The checkpoint's `current_state` is authoritative for the executor process and
state at which the test starts.

## Why use an executor checkpoint?

A targeted eval should test the interaction of interest without making every
run replay the entire Maternity Allowance journey. Starting the workflow from a
real executor checkpoint gives each repetition the same accumulated service
state while still exercising the real interpreter and agent.

A checkpoint is a **semantic SFSM checkpoint**, not a Temporal event-history
checkpoint. It contains the serialisable `InterpreterState` needed to resume
the journey, including:

- parent and child stack frames;
- frame variables and invocation inputs;
- transcript entries;
- environment values;
- the real interpreter step counter;
- metadata describing the current awaited input.

This matters for deeper interactions. For example, a section-4 checkpoint can
contain both the `main` frame and the active `section4_about_payment` frame,
including values accumulated in earlier sections. Reconstructing only the
current frame by hand would not faithfully represent a state the executor had
actually reached.

<<<<<<< HEAD
## Prerequisites

1. **Python 3.14+** and **uv** installed
2. **Temporal CLI** installed

```bash
brew install temporal
```

3. **AWS credentials** withbedrock:InvokeModel` permission for Claude Sonnet in your target region
4. **Workflow Server** & **Backend Stub Server** available, either:
   - Running locally
   - Deployed to AWS and accessible via its load balancer URL
=======
The snapshot is taken while the current `InputState` is already suspended at
step `N`. A new workflow must execute that input state again, so the runner
restores the checkpoint with step counter `N - 1`. The interpreter then
recreates step `N` and issues a fresh awaiting-input token. The captured
`awaiting` object is validation metadata rather than runtime state to restore.

## Conversation data
>>>>>>> 2ad802b (test case: start claim date today)

`conversation.json` contains the full user-visible conversation required to put
the agent in the same conversational context as the captured executor state.
The **final user message is the turn under test**. All preceding messages are
seeded into the agent's history.

The authoritative current executor prompt is supplied from the workflow
definition, so if that exact prompt is the final assistant message in the
conversation prefix the runner removes it from the seeded history before
sending the turn under test.

<<<<<<< HEAD
Verify your credentials are working:

```bash
aws sts get-caller-identity
```
=======
Only use deliberately synthetic journeys and conversations. A captured
interpreter state can contain everything entered earlier in the service
journey; do not commit checkpoints captured from real users or containing real
claimant PII.
>>>>>>> 2ad802b (test case: start claim date today)

## Running a test case

Run commands from `durable_poc/`.

<<<<<<< HEAD
### Local Ports Reference

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

### Terminal 2: Temporal Worker

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

### Terminal 3: Backend Stub Server

The worker executes HTTP activities that call backend services. Therefore, the service endpoint environment variables must be available in the same terminal session where the Temporal worker is running.

The stub server is currently deployed to AWS ECS under the `govuk-once-ailegibility-development` account.

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

### Terminal 4: Workflow Definition Server

The chat application retrieves workflow definitions from the Workflow Server.

The Workflow Server is currently deployed to AWS ECS under the `govuk-once-ailegibility-development` account.

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

Workflow definitions are served via:

```text
GET /api/v1/workflows/{id}
```

Verify that the server is responding using an endpoint known to exist in your deployment, for example:

```bash
curl http://localhost:8080/health
```

### Terminal 5: Agent Chat UI

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

## Configuration Reference

| Environment Variable | Default | Purpose |
| --- | --- | --- |
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server gRPC address |
| `WORKFLOW_SERVER_URL` | `http://localhost:8080` | Workflow definition server URL |
| `BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-6` | Claude model identifier in Bedrock |
| `AWS_REGION` | `eu-west-2` | AWS region used for Bedrock |
| `DVLA_BASE` | `http://localhost:8000` | DVLA service base URL |
| `POSTOFFICE_BASE` | `http://localhost:8000` | Post Office service base URL |
| `HMRC_BASE` | `http://localhost:8000` | HMRC service base URL |
| `DWP_BASE` | `http://localhost:8000` | DWP service base URL |

---

# Running the Terminal CLI Demo (Legacy)

The project also includes a terminal-based demo (`demo.py`) that executes workflows without using the chat interface.

This requires the following services to be running:

- Temporal Server
- Temporal Worker
- Stub Server
- Workflow Server

### Terminal 5: Interactive CLI

```bash
cd durable_poc
PYTHONPATH=. uv run python -m src.demo
```

You can then interact with workflows directly through the terminal instead of the web-based chat interface.
`
Follow the prompts in this terminal to step through the state machine.
---

## State Types Reference

* **`input`**: Suspends the workflow and exposes an awaited schema. Resumes when a matching payload is submitted via Update. Supports timeouts and retry counts.
* **`choice`**: Evaluates a list of rules (using operators like `eq`, `lt`, `is_true`, `not_empty`, `contains`) and branches execution.
* **`assign`**: Mutates the current stack frame's variable context (including date math like `date_subtract` and arithmetic `add`).
* **`call`**: Dispatches `http_call` activity with service validation, capture projections, error catches, and idempotency headers.
* **`invoke`**: Pushes a sub-process stack frame onto the workflow call stack, binding inputs and catch routes.
* **`output`**: Emits internal transcript messages or fires external notification activities.
* **`wait`**: Durably sleeps the workflow for an ISO 8601 duration string (e.g., `PT5M`).
* **`end`**: Terminates the current process frame with a status, outcome, and return payload.

## Targeted Maternity Allowance evaluation smoke run

The checkpoint runner exercises one real workflow interaction with the real
`WorkflowAgent` without replaying every earlier Maternity Allowance step. It
starts a fresh Temporal workflow from the scenario's interpreter checkpoint,
seeds the agent with the fixture's preceding user-visible conversation, sends
the final user message, waits for the executor's OTEL `InputState` span, converts
that span to the shared common-trace format, and evaluates the trace against the
scenario's `expected.submissions`.

Start Temporal and the worker with OTEL file export enabled, for example from
`durable_poc/`:
=======
Start Temporal and start the worker with OTEL file export enabled, for example:
>>>>>>> 2ad802b (test case: start claim date today)

```bash
mkdir -p .traces
OTEL_EXPORT_FILE="$PWD/.traces/durable-otel.jsonl" \
  uv run python -m src.worker
```

A scenario is invoked by its path relative to `evaluation/scenarios`, without
needing to name `scenario.yaml`:

```bash
uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/work_status_fixed_term_contract_ended
```

With the GDS AWS credentials wrapper:

```bash
gds-cli aws once-ailegibility-development-admin -- \
  uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/work_status_fixed_term_contract_ended
```

The other committed cases follow the same pattern:

```bash
uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/baby_not_born

uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/date_stopped_work_natural_language

uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/payment_frequency_fortnightly
```

An explicit case directory or `scenario.yaml` path is also accepted.

## Repeated runs

Use `--repeat` to measure stochastic reliability and `--concurrency` to bound
parallel calls:

```bash
uv run python -m evaluation.checkpoint_runner \
  maternity_allowance/work_status_fixed_term_contract_ended \
  --repeat 20 \
  --concurrency 4
```

Each repetition gets a fresh workflow ID and a freshly rehydrated
`InterpreterState`; repetitions do not share mutable workflow state.

Per-run artefacts are written beneath:

```text
.traces/evaluation-runs/<scenario-id>/<workflow-id>/
├── common.yaml
└── evaluation.json
```

Batch metadata, JSONL results and the aggregate summary are written beneath:

```text
.traces/evaluation-batches/<batch-id>/
├── batch.json
├── results.jsonl
└── summary.json
```

A semantic mismatch is a failed eval rather than a process crash. Execution or
trace-conversion errors are recorded separately as errors, so repeated evals
retain evidence for both passes and failures.

## Capturing or refreshing a real checkpoint

The interpreter exposes an evaluation-only `evaluation_checkpoint` Temporal
query. `capture_checkpoint.py` uses that query to save the real semantic state
of a synthetic journey while it is paused at the interaction you want to test.

First drive a deliberately synthetic journey in the normal application until
it is waiting at the target input, then note its Temporal workflow ID.

Capture directly into a case using its path relative to
`evaluation/scenarios`:

```bash
PYTHONPATH=. uv run python -m evaluation.capture_checkpoint \
  <workflow-id> \
  --scenario maternity_allowance/date_stopped_work_natural_language
```

You can also capture the checkpoint **before creating the test case**. For
example, if neither the directory nor `scenario.yaml` exists yet:

```bash
PYTHONPATH=. uv run python -m evaluation.capture_checkpoint \
  <workflow-id> \
  --scenario maternity_allowance/claim_start_date_today
```

This creates
`evaluation/scenarios/maternity_allowance/claim_start_date_today/` and writes
`checkpoint.json` into it. It deliberately does not invent `scenario.yaml` or
`conversation.json`; add those afterwards when you define the conversation and
expected submission.

When an existing checkpoint is present, the command uses its
`current_state.process_id` and `current_state.state_id` to verify that the live
workflow is paused at the same semantic interaction before overwriting it. If a
`scenario.yaml` already exists but the checkpoint does not, a single
`expected.submissions` entry is used as a partial state-ID validation before the
first checkpoint is written. If neither file exists yet, the first capture has
no pre-existing semantic target to validate against.

You can also capture to an explicit path without a scenario:

```bash
PYTHONPATH=. uv run python -m evaluation.capture_checkpoint \
  <workflow-id> \
  --output evaluation/scenarios/maternity_allowance/my_new_case/checkpoint.json
```

When capturing a new case this way, inspect `current_state`, `awaiting`, and the
stack frames before committing it. In particular, confirm that the process and
state are the intended interaction and that nested subprocess frames are
present where expected.

## Trace conversion and scoring

The worker writes implementation-specific OTEL JSONL. The durable converter
selects spans for the workflow ID and for the process/state recorded in the
case's `checkpoint.json`, then emits common semantic events such as:

```yaml
events:
  - type: interaction_available
    interaction_id: prompt_reason_stopped_work
  - type: values_submitted
    interaction_id: prompt_reason_stopped_work
    values:
      reason_stopped_work: resigned_or_redundant
```

`conversation.json` supplies the fixture ID/version recorded in
`initial_context`; its bytes are hashed into the common trace for provenance.
The runner then evaluates the common trace against `scenario.yaml`.

The converter can also be invoked directly:

```bash
uv run python -m evaluation.otel_common_trace \
  .traces/durable-otel.jsonl \
  maternity_allowance/baby_not_born \
  --workflow-id <workflow-id> \
  --output .traces/<workflow-id>.common.yaml
```

## Relationship to shared evaluation code

The common trace vocabulary and deterministic evaluator remain shared in the
sibling `agents` package. The Maternity Allowance cases live here because their
captured SFSM checkpoints are specific to the durable implementation.

Shared implementation-independent scenarios, such as the DVLA comparison
scenarios, remain under `agents/evaluation/scenarios/` and continue to declare
`input.conversation_fixture`. The shared evaluator checks that identity when it
is present. Durable scenarios omit it because the colocated
`conversation.json` convention is validated by the durable runner.

This keeps the distinction explicit:

- **shared scenario**: behaviour any implementation can be expected to exhibit;
- **durable scenario case**: a targeted behaviour plus the durable executor
  state required to reproduce that interaction.

## Design principles

- **One directory is one reproducible eval case.** The expectation,
  conversation, and executor state should move together.
- **Do not duplicate conventional paths in YAML.** `scenario.yaml`,
  `conversation.json`, and `checkpoint.json` have fixed meanings.
- **The captured checkpoint owns the executor target.** Do not duplicate
  process/state identifiers in scenario configuration.
- **Prefer semantic checkpoints over infrastructure histories.** Save the SFSM
  state needed to resume the service, not Temporal event history, unless
  Temporal behaviour itself is under test.
- **Use the real agent and interpreter.** The targeted runner shortens setup; it
  should not replace the system under evaluation with mocks.
- **Keep failure evidence.** Failed model behaviour is an eval result worth
  retaining, not a reason to discard the run.
