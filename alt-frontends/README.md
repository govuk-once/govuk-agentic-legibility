# durable-frontend

SvelteKit UI for four interaction styles over the same Temporal-executed
workflow contract: `/web` (form-driven), `/chat` (natural-language),
`/agentic` (autonomous, profile-driven), `/voice` (speech in/out).

## Architecture

`durable_poc` (Python) owns Temporal and is the only source of truth for
workflow execution: it runs the FSM interpreter, exposes the run lifecycle
(`/api/v1/runs`, `/api/v1/workflows`, `/api/v1/profiles`) over its FastAPI
app, and proxies the workflow-definition catalogue from a separate
"workflow server". See `src/lib/api/client.ts` — every function that calls
`getApiBaseUrl()` (default `http://127.0.0.1:8010`) is talking to `durable_poc`.

Everything LLM-related, by contrast, lives **in this app**, not in
`durable_poc`, as same-origin SvelteKit routes under `src/routes/api/`:

- `/api/chat` — the `/chat` route's tool-calling agent loop (replaces
  `durable_poc/agent/api/routes/chat_ws.py`'s WebSocket).
- `/api/agentic/[workflowId]/autonomy` and `.../autonomy/resume` — the
  `/agentic` route's autonomous stepper (replaces
  `durable_poc/agent/api/routes/agentic.py`).
- `/api/web/[workflowId]/prefill` and `.../context` — `/web`'s opt-in LLM
  pre-fill suggestions.
- `/api/voice/transcribe` and `/api/voice/speak` — server-side AWS
  Transcribe Streaming / Polly for `/voice`.

The agent loop itself (`src/lib/server/agent/`) calls Bedrock by default, or
OpenRouter if `OPENROUTER_API_KEY` is set, and drives the workflow forward by
calling straight back into `durable_poc`'s `/api/v1/runs` endpoints
(`startRun`/`getRunState`/`submitRunInput` in `client.ts`) — so Temporal
stays authoritative and this app never mutates run state directly. This
split means **this app's own `.env`** needs the AWS/Bedrock/OpenRouter
credentials, not `durable_poc`'s — see [Environment variables](#environment-variables).

## Bringing up the stack

Run these in order, from the repo root (`govuk-agentic-legibility/`), using the
`Justfile` there.

1. **Temporal dev server** — not managed by this repo; needs the
   [Temporal CLI](https://docs.temporal.io/cli) installed locally.

   ```bash
   temporal server start-dev
   ```

   Must be listening on `localhost:7233` before anything else starts.

2. **Workflow definition/catalogue server** (port 8080) — serves
   `GET /api/v1/workflows` and `/api/v1/workflows/{id}`. This service is **not
   part of this checkout** — `durable_poc/agent/tools.py` and `deps.py` just
   proxy to `WORKFLOW_SERVER_URL` (defaults to `http://localhost:8080`).
   Point that env var at wherever it actually runs, or start it separately.

3. **Temporal worker** — executes the FSM interpreter; must be running for any
   workflow to progress.

   ```bash
   just build          # uv sync, if you haven't
   cd durable_poc && uv run python -m src.worker
   ```

4. **durable_poc's API** — what this frontend talks to for the run lifecycle
   (port 8010, matches `PUBLIC_DURABLE_API_URL` below).

   ```bash
   just durable-api
   ```

5. **This frontend** — SvelteKit dev server (port 5173, matches the CORS
   origins hardcoded in `durable_poc/agent/api/app.py`).

   ```bash
   just durable-frontend-install   # first time only
   just durable-frontend
   ```

   Equivalent without `just`: `pnpm install` then `pnpm dev` from this
   directory.

## Working without the executor (mock mode)

To work on the UI without Temporal, the worker, `durable_poc`'s API or the
workflow server running:

```bash
pnpm dev:mock
```

This serves a stand-in executor from this app at `/mock-api/api/v1/...` and
points `PUBLIC_DURABLE_API_URL` at it, so `client.ts`, `sse.ts` and the
server-side agent tools behave exactly as they do against `durable_poc`. None
of the rest of the stack is touched — plain `pnpm dev` is unchanged, and the
`/mock-api` routes 404 unless `DURABLE_MOCK=1`.

What it does (`src/lib/server/mock-executor/`):

- **Workflows** are the real `*_schema.json` definitions, read from
  `DURABLE_POC_ROOT`, so edits there show up on the next request.
- **Runs** are executed by an in-memory TypeScript port of
  `src/interpreter.py` (same predicates, validation messages, tokens and
  transcript `[ENGINE LOG]` lines), and the SSE feed mirrors
  `agent/api/events.py:watch_run`.
- **Downstream services** (DWP, HMRC, DVLA, Post Office) return canned
  happy-path responses from `services.ts`. Edit a stub there to exercise an
  error branch; anything unstubbed returns 503 and follows the call's `catch`.
- **Resumable runs**: each `evaluation/scenarios/*/*/checkpoint.json` is
  restored as a mid-journey run on startup (stable ids, so they survive
  restarts), giving the run pickers something to show.

Differences from the real executor: `wait` states are skipped, notification
channels other than `transcript` are ignored, input timeouts longer than ~24
days never fire, and runs are lost when the dev server restarts. LLM routes
(`/chat`, `/agentic`, `/web` prefill, `/voice`) still need Bedrock/OpenRouter
or AWS credentials.

## Environment variables

Copy `.env.example` to `.env` and fill in what each route you're using needs.
All of these are read by **this app**, not `durable_poc`.

| Variable | Default | Used by |
|---|---|---|
| `PUBLIC_DURABLE_API_URL` | `http://127.0.0.1:8010` | Every route — base URL for `durable_poc`'s run/workflow/profile API. |
| `DURABLE_POC_ROOT` | `../durable_poc` | `/agentic`'s profile-fixture loader, reads `evaluation/scenarios/<fixture>/conversation.json` straight off disk. Mock mode also reads workflow definitions and checkpoints from here. |
| `DURABLE_MOCK` | unset | Set to `1` to enable the `/mock-api` stand-in executor. `pnpm dev:mock` sets this (and `PUBLIC_DURABLE_API_URL`) for you. |
| `BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-5` | `/chat`, `/agentic`, `/web` prefill — the default LLM path (via AWS Bedrock). |
| `AWS_REGION` | `us-east-1` | Bedrock, and `/voice`'s Transcribe/Polly calls (shared AWS credential provider chain). |
| `OPENROUTER_API_KEY` | unset | Dev-only override: when set, routes `/chat`/`/agentic`/`/web` LLM turns through OpenRouter instead of Bedrock. Never set in production. |
| `OPENROUTER_MODEL_ID` | `anthropic/claude-sonnet-5` | Paired with `OPENROUTER_API_KEY`. |
| `TRANSCRIBE_LANGUAGE_CODE` | `en-GB` | `/voice`'s speech-to-text. |
| `POLLY_VOICE_ID` | `Amy` | `/voice`'s text-to-speech. |

`/voice` and Bedrock both need real AWS credentials available to the process
(the default AWS SDK credential provider chain — env vars, `~/.aws/credentials`,
an instance role, etc.) in addition to the vars above.

## Project layout

- `src/routes/{web,chat,agentic,voice}` — the four front doors' pages.
- `src/routes/api/` — this app's own backend: the chat/agentic agent loops,
  `/web` prefill, and `/voice` STT/TTS proxies (see Architecture above).
- `src/lib/api/client.ts` — typed client for `durable_poc`'s REST API, plus
  the same-origin fetches to this app's own `api/` routes.
- `src/lib/api/sse.ts` — `EventSource` wrapper for watching a run's live
  transcript/trace events.
- `src/lib/server/agent/` — the LLM tool-calling loop shared by `/chat` and
  `/agentic` (`run-turn.ts` dispatches to `run-loop-bedrock.ts` or
  `run-loop-openrouter.ts`; `tool-defs.ts`/`tools.ts`/`agentic-tools.ts`
  define what the model can call).
- `src/lib/components/forms/` — one component per JSON-schema `kind`
  (`StringField`, `BooleanField`, `SelectOneField`, `SelectManyField`,
  `FileRefField`), dispatched by `KindField.svelte`; this is what every
  front door renders a human-input prompt as.
- `src/lib/graph/` — dagre-based layout and Svelte nodes for `/agentic`'s
  live workflow visualisation (ported from `service_studio_frontend`).
- `src/lib/audio/pcm-recorder.ts` — browser-side mic capture for `/voice`,
  using an `AudioWorklet` to produce 16kHz mono PCM16 (not `MediaRecorder`,
  since its container formats aren't ones Transcribe Streaming accepts).
- `static/gov.css`, `static/govuk-extras.css` — GOV.UK Frontend plus local
  additions, including the `ss-*` utility classes matching
  `service_studio_frontend`'s design language (cards, panels, the blue CTA).

## Other commands

```bash
just durable-frontend-check   # svelte-check, 0 errors expected
just durable-frontend-build   # production build (adapter-node)
```

Without `just`: `pnpm check`, `pnpm build`, `pnpm preview`. There is no
frontend test suite yet — `durable_poc`'s own tests
(`durable_poc/tests/`) and evaluation harness (`durable_poc/evaluation/`)
cover the executor/agent behaviour this app talks to.
