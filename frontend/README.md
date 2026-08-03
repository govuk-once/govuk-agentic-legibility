# Journey executor frontend

This SvelteKit application is a developer-facing demonstration of an agent-assisted,
deterministic service journey. It renders the current interaction from its JSON Schema,
allows an agent to propose values from natural language or retrieve approved journey
guidance, and requires the user to review or edit values before the executor submits
them.

The developer panel exposes:

* the browser-facing run state;
* the exact current interaction supplied to the agent;
* the validated structured agent result;
* guidance tool requests and retrieved document provenance;
* the service-selected interaction sequence;
* the ordered raw JSONL application and transport trace.

It deliberately contains no journey-specific branching. The browser sends a run ID and
the reviewed values for the current interaction to the Python HTTP adapter. The executor
retains the continuation token and follows the operation advertised by the journey
service. The agent never receives either value.

## Run the frontend locally

By default, the frontend and executor run locally against the deployed DVLA-like journey
service. This requires two local processes:

1. the Python executor and agent API on port 8001;
2. the SvelteKit frontend on port 5173.

A local version of the journey service can also be used, as described in
[Run against a local journey service](#run-against-a-local-journey-service).

### Configure the interaction assistant

Add an available Bedrock model or inference-profile ID to `agents/.env`:

```dotenv
JOURNEY_AGENT_MODEL_ID=<Bedrock model or inference-profile ID>
JOURNEY_AGENT_REGION=eu-west-2
```

The region defaults to `eu-west-2` if you don't set it but `JOURNEY_AGENT_MODEL_ID` is needed. An example config might be:

```dotenv
JOURNEY_AGENT_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0
JOURNEY_AGENT_REGION=eu-west-2
```

The Python API needs AWS credentials with permission to invoke the configured Bedrock
model.

### 1. Start the executor and agent API

Run the API through the appropriate `aws-vault` or `gds-cli` profile. For example:

```bash
gds-cli aws <profile> -- just api
```

Without a `STUB_SERVER_URL`, the executor uses the deployed journey service. The API listens on http://127.0.0.1:8001.

Its OpenAPI documentation is available at
http://127.0.0.1:8001/docs.

The API process loads agent configuration from `agents/.env`. Restart it after
changing the model configuration. Active journey runs are held in memory, so restarting this process clears any
journey currently in progress.

### 2. Start the frontend

Install the frontend dependencies once:

```bash
just frontend-install
```

Then start the SvelteKit development server:

```bash
just frontend
```

Open http://127.0.0.1:5173.

The frontend uses the executor API at `http://127.0.0.1:8001` by default. Override
this when necessary with:

```bash
PUBLIC_JOURNEY_API_URL=<URL> just frontend
```

## Presentation modes

The same SvelteKit application can be opened in two presentation modes.

Agent-assisted mode is the default. It loads conversation fixtures, displays values
proposed by the Bedrock-backed assistant, answers journey questions using the guidance
operations advertised by the journey service, and shows the developer panel:

```text
http://127.0.0.1:5173/
```

No-agent mode starts without a conversation fixture and explicitly disables agent
assistance for the run. The frontend only renders the current JSON Schema and submits
the completed form to the same executor and DVLA-like journey API:

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

## Demonstrate journey guidance

In assisted mode, select the **Question about postcode lookup for a flat** fixture, or
enter the following beneath the current form:

```text
Should I use postcode lookup if I live in a flat?
```

The agent can list the compact guidance directory and retrieve a relevant Markdown
document from the journey service. The answer is displayed without submitting the form
or changing the current journey interaction. The developer trace shows the
model-selected tool calls, the corresponding HTTP exchanges, and the retrieved document
ID, version and content hash.

If the model answers without retrieving guidance, the answer is still displayed and the
trace records `grounded_in_retrieved_guidance: false`; automated evals can score this as
a model-behaviour failure rather than a runtime error.

A single message can also ask a question and express a form preference. For example:

```text
Can I use postcode lookup if I live in a flat? If so, I would like to use it.
```

The assistant may return `answer_journey_question` followed by `propose_values` in one
structured response. The guidance answer is displayed and the corresponding form value
is proposed, but the user must still review and submit the form.

## Run without agent assistance

Use no-agent mode when demonstrating the journey without an agent, even when the API has
a Bedrock model configured:

```text
http://127.0.0.1:5173/?mode=noagent
```

The deterministic journey and manual form entry also work when no Bedrock model is
configured.

When using the local mock journey service, the API can therefore be started without AWS
credentials:

```bash
STUB_SERVER_URL=http://127.0.0.1:8000 just api
```

## Local traces

Each journey run writes a JSONL trace to `.traces/`.

The trace includes:

* journey-service requests and responses;
* user messages sent for agent assistance;
* structured agent actions;
* requested and completed guidance tools;
* guidance answers and observed retrieval provenance;
* values reviewed and submitted by the user;
* terminal completion or failure events.

The developer panel in the frontend displays the same trace while the journey is
running.

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

## Run against a local journey service

To run the entire prototype locally (e.g. if you have made changes to the mocked DVLA journey which are not yet deployed), start the DVLA-like mock journey service and
configure the executor to use it instead of the deployed service.

This adds a third local process on port 8000.

### 1. Start the mock journey service

From a checkout of
[`the mocked DVLA journey repo`](https://github.com/govuk-once/stub-flex-legibility):

```bash
just run
```

Leave this running in its own terminal.

### 2. Start the executor and agent API

Start the API as described above, but set `STUB_SERVER_URL` to the local service:

```bash
gds-cli aws <profile> -- env \
  STUB_SERVER_URL=http://127.0.0.1:8000 \
  just api
```

The frontend setup is unchanged and still connects to the executor API on port 8001.

The mock journey service itself can be run entirely locally. AWS credentials are needed
only when the configured interaction assistant uses Bedrock.
