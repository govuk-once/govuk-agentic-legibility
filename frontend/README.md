# Journey executor frontend

This SvelteKit application is a developer-facing demonstration of an agent-assisted,
deterministic service journey. It renders the current interaction from its JSON Schema,
allows an agent to propose values from natural language, and requires the user to review
or edit those values before the executor submits them.

The developer panel exposes:

- the browser-facing run state;
- the exact current interaction supplied to the agent;
- the validated structured agent result;
- the service-selected interaction sequence;
- the ordered raw JSONL application and transport trace.

It deliberately contains no journey-specific branching. The browser sends a run ID and
the reviewed values for the current interaction to the Python HTTP adapter. The executor
retains the continuation token and follows the operation advertised by the journey
service. The agent never receives either value.

## Run locally
The prototype consists of three processes:

1. the DVLA-like mock journey service on port 8000;
2. the Python executor and agent API on port 8001;
3. the SvelteKit frontend on port 5173.

### Configure the interaction assistant

Add an available Bedrock model or inference-profile ID to `agents/.env`:

```dotenv
JOURNEY_AGENT_MODEL_ID=<Bedrock model or inference-profile ID>
JOURNEY_AGENT_REGION=eu-west-2
```

The region defaults to `eu-west-2`, but setting it explicitly makes the local
configuration easier to understand.

The Python API needs AWS credentials with permission to invoke the configured
Bedrock model. The mock journey service can still be run entirely locally.

### 1. Start the mock journey service

From a checkout of
[`stub-flex-legibility`](https://github.com/govuk-once/stub-flex-legibility):

```bash
uv run uvicorn src.server:app --reload --port 8000
```

Leave this running in its own terminal.

### 2. Start the executor and agent API

From this repository, run the API through the appropriate `aws-vault` or `gds-cli` profile e.g.:

```bash
gds-cli aws <profile> -- env \
  STUB_SERVER_URL=http://127.0.0.1:8000 \
  just api
```

The API listens on [http://127.0.0.1:8001](http://127.0.0.1:8001).

Its OpenAPI documentation is available at
[http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

The API process loads agent configuration from `agents/.env`. Restart it after
changing the model configuration.

Active journey runs are held in memory, so restarting this process clears any
journey currently in progress.

### 3. Start the frontend

Install the frontend dependencies once:

```bash
just frontend-install
```

Then start the SvelteKit development server:

```bash
just frontend
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

### Presentation modes

The same SvelteKit application can be opened in two presentation modes.

Agent-assisted mode is the default. It loads conversation fixtures, displays values
proposed by the Bedrock-backed assistant, and shows the developer panel:

```text
http://127.0.0.1:5173/?mode=assisted
```

No-agent mode starts without a conversation fixture and explicitly disables agent
assistance for the run. The frontend only renders the current JSON Schema and submits the
completed form to the same executor and DVLA-like journey API:

```text
http://127.0.0.1:5173/?mode=noagent
```

The developer panel is shown by default in both modes so the same executor state and
raw trace remain visible when comparing them. Hide it explicitly in either mode with:

```text
http://127.0.0.1:5173/?mode=noagent&developer=false
http://127.0.0.1:5173/?mode=assisted&developer=false
```

A no-agent-mode run is labelled `noagent_web_frontend` in its raw trace. It does not
load conversation fixtures, add conversation messages or invoke the interaction
assistant. This makes it suitable for demonstrating that the same server-driven journey
can be consumed as an ordinary web service.


The frontend defaults to using the executor API at
`http://127.0.0.1:8001`. Override this when necessary with:

```bash
PUBLIC_JOURNEY_API_URL=<URL> just frontend
```

### Run without agent assistance

Use no-agent mode when demonstrating the journey without an agent, even when the
API has a Bedrock model configured:

```text
http://127.0.0.1:5173/?mode=noagent
```

The deterministic journey and manual form entry also work when no Bedrock model is
configured. In that case, start the API without AWS credentials:

```bash
STUB_SERVER_URL=http://127.0.0.1:8000 just api
```

## Run against the deployed server

Follow the local instructions but do not provide a local stub server URL. For example:

```bash
gds-cli aws <profile> -- env just api
```

### Local traces

Each journey run writes a JSONL trace to `.traces/`.

The trace includes:

* journey-service requests and responses;
* user messages sent for agent assistance;
* structured agent proposals;
* values reviewed and submitted by the user;
* terminal completion or failure events.

The developer panel in the frontend displays the same trace while the journey
is running.

`.traces/` is ignored by Git and may contain user-entered information.

## Checks

```bash
just frontend-check
just frontend-build
```

The existing `just check` remains the Python suite. `just check-all` runs the Python and
frontend checks after frontend dependencies have been installed.

## Renderer scope

The prototype supports booleans, strings, nullable strings, string enums, integers,
numbers, required-field checks, and semantic content data used for review summaries.
Unsupported schema types are displayed explicitly instead of being silently ignored.
