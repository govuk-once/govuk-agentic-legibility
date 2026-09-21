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
        ├── claim_start_date_today/
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

### Dynamic expected values

Expected values are literal by default. For date values that are intentionally
relative to the time of the eval run, use `$relative_date`:

```yaml
expected:
  submissions:
    prompt_flexible_start_date:
      values:
        chosen_ma_start_date:
          $relative_date:
            days: 0
            format: "%d/%m/%Y"
            timezone: "Europe/London"
```

The evaluator resolves this against `common_trace.run.started_at`, not the wall
clock at evaluation time. This means a saved common trace can be re-evaluated
later and will produce the same expected date. `days` is an integer offset from
the run date in the requested IANA timezone; `0` means the run's local calendar
date.

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

The snapshot is taken while the current `InputState` is already suspended at
step `N`. A new workflow must execute that input state again, so the runner
restores the checkpoint with step counter `N - 1`. The interpreter then
recreates step `N` and issues a fresh awaiting-input token. The captured
`awaiting` object is validation metadata rather than runtime state to restore.

## Conversation data

`conversation.json` contains the full user-visible conversation required to put
the agent in the same conversational context as the captured executor state.
The **final user message is the turn under test**. All preceding messages are
seeded into the agent's history.

The authoritative current executor prompt is supplied from the workflow
definition, so if that exact prompt is the final assistant message in the
conversation prefix the runner removes it from the seeded history before
sending the turn under test.

Only use deliberately synthetic journeys and conversations. A captured
interpreter state can contain everything entered earlier in the service
journey; do not commit checkpoints captured from real users or containing real
claimant PII.

## Running a test case

Run commands from `durable_poc/`.

Start Temporal and start the worker with OTEL file export enabled, for example:

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
  maternity_allowance/claim_start_date_today

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
