# GOV.UK Forms Frontend

A GOV.UK Forms-style frontend that renders converted GOV.UK Forms using the
existing Temporal-based agent and deterministic SFSM journey interpreter.

## Architecture

```
                  forms_frontend/
                       |
             +---------+---------+
             |                   |
        frontend/            api/
      (Svelte + GOV.UK     (FastAPI)
       Frontend)                |
             |                  |
             +--------+---------+
                      |
              EXISTING durable_poc
                      |
            +---------+---------+
            |                   |
      Existing agent     Existing Temporal
      (Bedrock/Strands)  worker/interpreter
            |                   |
         Bedrock             SFSM
                               |
                         OTEL tracing
```

The frontend is a **presentation and interaction layer only**. All journey
progression goes through the existing Temporal interpreter. The frontend
never independently calculates the next state.

## Components

### `api/` — Thin HTTP API (FastAPI)

Imports existing `durable_poc/agent/tools.py` functions directly.
No journey logic is duplicated.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/forms` | List available forms from workflow server |
| GET | `/api/forms/{id}` | Get form definition and metadata |
| POST | `/api/sessions` | Start a new form session (creates Temporal workflow) |
| GET | `/api/sessions/{id}/state` | Get current question + presentation metadata |
| POST | `/api/sessions/{id}/submit` | Submit answer to current question |
| POST | `/api/sessions/{id}/chat` | Send message to the agent |
| POST | `/api/sessions/{id}/propose` | Request agent answer proposal |
| POST | `/api/sessions/{id}/confirm-proposal` | Accept proposed answer |
| POST | `/api/sessions/{id}/reject-proposal` | Reject proposal (answer manually) |
| PUT | `/api/sessions/{id}/policy` | Change interaction policy and final-review preference |
| POST | `/api/sessions/{id}/review/amend` | Validate a review edit through a new Temporal workflow |
| POST | `/api/sessions/{id}/review/confirm` | Accept the reviewed answers as final |
| POST | `/api/sessions/{id}/files?token=...` | Opt-in local synthetic-file upload for an active file question |

### `frontend/` — GOV.UK Forms UI (Svelte + GOV.UK Frontend)

Renders form questions using GOV.UK Frontend components based on the
`answer_type` and `answer_settings` preserved by the forms compiler.

**Supported answer types:**
- `selection` → Radio buttons (select_one) / checkboxes (select_many)
- `text` (single_line) → Text input
- `text` (long_text) → Textarea
- `email` → Email input
- `name` → First name / last name fields (concatenated for submission)
- `date` → Day / month / year fields
- `address` → Multi-line UK address fields
- `national_insurance_number` → NI number input with hint
- `organisation_name` → Text input
- `number` → Numeric input
- `boolean` → Yes / No radio buttons
- `file_ref` → Opt-in local file upload (synthetic files only; max 10 MiB)

### Local file-upload testing

The older `durable_poc/agent/chat.py` upload control sends filename, type and
byte-count metadata, not actual file bytes. This frontend can store synthetic
file bytes locally before submitting an opaque `file_ref` to Temporal. Opt in:

```bash
FORMS_ENABLE_DEV_UPLOADS=1 \
FORMS_UPLOAD_DIR=/tmp/forms-synthetic-uploads \
PYTHONPATH=durable_poc:. uv run python -m forms_frontend.api.main
```

This is a local-only development feature, **not** production document storage.
Only upload synthetic files. Uploaded files remain on disk until you delete
them manually. The endpoint is disabled by default, restricted to loopback,
and verifies the current Temporal input token. The API rejects invented file
references that were not uploaded in the same session and question.

### Interaction Policies

**Manual:** User completes the form normally. Agent available for questions.

**Confirm:** Agent proposes answers from conversation. User confirms or edits
before submission.

**Automatic:** Agent submits answers it's confident about, skipping questions
it can answer. Stops when information is missing. Shows a log of
auto-answered questions for review. If the agent runs out of information, the
current GOV.UK question stays visible **without switching out of Automatic
mode**. Submitting an answer manually resumes automatic completion from the
next Temporal input. The user can also select "Try automatic completion again"
after adding information through chat. This only retries the current question;
it never replays already accepted Temporal inputs.

**Automatic with final review (enabled by default in the frontend):** The
assistant fills in as many questions as it can, handing missing details to the
user as before. Once Temporal has finished collecting answers, the frontend
shows a GOV.UK-style Check your answers page listing **all accepted answers**,
including those supplied manually, with Change links. An independent checkbox
allows Automatic without final review. The mode controls who answers each
question; the checkbox controls whether final approval is requested.

Changing an answer at review uses **the existing SFSM interpreter**: the API
starts a fresh Temporal run using the original definition and replays the
accepted answers with the correction. It swaps runs only after Temporal accepts
the revised answer. If branching changes or an old downstream answer fails
validation, the frontend requests the newly required information and returns
to final review on completion. Replayed answers retain their original source;
an automatically generated answer changed by the user is counted as manual.

The prototype collects answers but **does not submit them to a department**:
final review therefore gates acceptance of the collected form, not any real
service-side submission. Review/replay is deliberately unavailable for
journeys with service actions or other potentially non-idempotent operations.
Previously uploaded synthetic files can be retained in a replay but cannot be
replaced from the review page. The history and review flag are in-memory POC
session data; they are lost on server restart.

The frontend's dependency-free auto-progress regression tests can be run with
`cd forms_frontend/frontend && npm run test:unit` (Node 18+).

## Prerequisites

These are the same services the existing `durable_poc` agent requires:

1. **Temporal server** running on localhost:7233
2. **Workflow definition server** (spike-legibility-workflow-server) with
   filesystem mode pointing to compiled forms
3. **Temporal worker** (`durable_poc/src/worker.py`)
4. **AWS credentials** for Bedrock access (agent features only)

## Setup

```bash
# From the repository root:

# Install frontend dependencies
cd forms_frontend/frontend
npm install
npm run setup-govuk
npm run build
cd ../..
```

## Running

### Terminal 1 — Temporal server
```bash
temporal server start-dev
```

### Terminal 2 — Workflow definition server (separate repo)
```bash
cd spike-legibility-workflow-server
WORKFLOW_SOURCE=filesystem \
WORKFLOW_DIR=/absolute/path/to/compiled_forms \
just run
```

### Terminal 3 — Temporal worker
```bash
cd durable_poc
PYTHONPATH=. \
DWP_BASE=http://127.0.0.1:8000 \
HMRC_BASE=http://127.0.0.1:8000 \
OTEL_EXPORT_FILE="$PWD/.traces/durable-otel.jsonl" \
uv run python -m src.worker
```

### Terminal 4 — Forms frontend API
```bash
# From repository root
gds-cli aws <account-name> \
  env \
    PYTHONPATH=durable_poc:. \
    AWS_REGION=eu-west-2 \
    BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-6 \
    WORKFLOW_SERVER_URL=http://localhost:8080 \
    FORMS_FRONTEND_PORT=8090 \
    uv run python -m forms_frontend.api.main
```

### Terminal 5 — Frontend dev server (development only)
```bash
cd forms_frontend/frontend
npm run dev
```

Then open http://localhost:5173 (development) or http://localhost:8090 (production build).

### Without AWS credentials (manual mode only)

The API server starts and serves forms without agent features. Use manual
policy — the chat and proposal features require Bedrock access.

```bash
PYTHONPATH=durable_poc:. \
WORKFLOW_SERVER_URL=http://localhost:8080 \
uv run python -m forms_frontend.api.main
```

## Testing

```bash
# From repository root — no live services required
PYTHONPATH=durable_poc:. uv run pytest forms_frontend/tests/ -v
```

Tests mock Temporal and Bedrock. They verify:
- Loading compiled form definitions (forms 2130 and 6)
- Starting Temporal workflows
- Submitting string, boolean, and select_one values
- Optional field handling
- Stale token rejection
- Presentation metadata preservation
- Deterministic routing in form 2130
- Proposal response parsing and value coercion
- Policy changes

## Test Forms

### Form 2130 — "Give feedback on Search for local land charges"

9-question feedback form with two conditional branches:
- Boolean branch: "Did you receive assistance?" → No skips to email question
- Select branch: "Who provided assistance?" → friend/colleague skips to email

### Form 6 — "Amend my claim for holiday pay accrued"

11-question linear form exercising diverse input types:
name, text, NI number, email, date, address, organisation, numbers.

## What's Implemented

- GOV.UK Forms-style frontend using GOV.UK Frontend components
- Integration with existing Temporal-based runtime (no new interpreter)
- Integration with existing agent (Strands/Bedrock)
- Manual, confirm, and automatic interaction policies
- Optional, default-on final review in Automatic mode with Change links
- Rendering of converted forms using existing presentation metadata
- All answer types found in forms 6 and 2130
- Chat interface alongside the form
- Auto-progress log for reviewing agent-answered questions
- 35 focused automated tests
- Stale token and validation error handling

## What's Not Yet Implemented

- Departmental file-upload integration and production storage/access controls
- Checkboxes for select_many — currently renders as radios
- Full GOV.UK Forms Runner visual fidelity (some layout differences)
- Page heading / guidance markdown rendering
- Declaration page before final submission
- Production session persistence (currently in-memory)
- WebSocket for real-time agent updates (currently uses HTTP polling via
  refresh-after-submit)

## Existing System Unchanged

- `durable_poc/src/interpreter.py` — not modified
- `durable_poc/src/worker.py` — not modified
- `durable_poc/agent/` — not modified (imported directly)
- `durable_poc/agent/chat.py` — still works on port 7860
- OpenTelemetry tracing — preserved
- Compiled forms — not modified
