# Server-driven journey executor

This package contains a proof-of-concept executor for testing server-driven service
journeys on the [Flex Mock API Server](https://github.com/govuk-once/stub-flex-legibility)
using protocol 2.0.

The executor exposes stepwise operations that can be driven by a CLI, web application,
agent or automated test harness. It starts an advertised journey, returns the current
interaction, and submits a result to the next operation selected by the service.

Its purpose is to demonstrate that a journey can be completed predictably without the
client encoding the workflow graph or branching rules. It is not itself a user-facing
interface, an agent implementation or a production workflow service.

The service, rather than the executor, owns journey progression. The executor:

1. retrieves the journey catalogue;
2. starts an advertised journey;
3. returns the current `interaction` to its consumer;
4. accepts a result from that consumer;
5. submits the result to the advertised `next_action`, carrying the latest
   `continuation_token`;
6. returns the service's next interaction or terminal response.

It does not branch on journey status, interaction identifiers or domain values and does
not load or interpret a workflow graph.

## Stepwise operations

The core executor does not own an input loop. A consumer can pause for user input, call
an agent, render a web interface or load a test fixture between operations:

```python
from agents.src.workflow_executor import JourneyClient, JourneyExecutor

executor = JourneyExecutor(JourneyClient("http://127.0.0.1:8000"))

response = executor.start("change-driving-licence-address")
interaction = executor.current_interaction(response)

response = executor.submit(
    response,
    {"use_postcode_lookup": True},
)
```

`current_interaction()` returns `None` for a terminal response. Terminality and the
field names needed to continue are read from the protocol definition advertised in the
service catalogue:

```python
while not executor.is_terminal(response):
    interaction = executor.current_interaction(response)
    result = consumer.collect(interaction)
    response = executor.submit(response, result)
```

The loop belongs to the consumer. The bundled CLI implements this loop for manual
development, while a SvelteKit backend adapter, agent or evaluation harness can drive
the same operations differently.

## Run against a local stub server

Start `stub-flex-legibility` locally on port 8000, then run from this repository root:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  change-driving-licence-address
```

At each interaction the CLI displays the semantic content and input JSON Schema. Enter
a JSON object matching that schema, for example:

```json
{"use_postcode_lookup": true}
```

Followed by:

```json
{"postcode": "BS1 3AB", "building_number_or_name": "18"}
```

And finally:

```json
{"confirmed": true}
```

## Use the deployed stub

Set `USE_STUB_SERVER=1` in `agents/.env`. The CLI loads that file automatically and
retrieves the base URL from the existing `/flex-mock/server-url` Parameter Store entry:

```sh
uv run python -m agents.src.workflow_executor.cli \
  change-driving-licence-address
```

`STUB_SERVER_URL` can be used as a direct environment-variable override. Values already
present in the process environment take precedence over `agents/.env`.

## Record a raw local trace

Pass `--trace-dir` to save the transport evidence from a run as a local JSON Lines file:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --trace-dir .traces \
  change-driving-licence-address
```

The trace contains a run-start event, every journey-service HTTP request and response,
and a final event indicating whether the run reached a terminal response or stopped at
an interaction limit. Continuation-token values are redacted using the field names in
the advertised protocol, while submitted results and service response bodies are kept
for later evaluation.

`.traces/` is ignored by Git. Traces are local development artefacts and may contain
user-entered values. Sanitised examples selected for tests should be copied to an
explicit committed fixture directory rather than removing this ignore rule.

## Save the latest response

The CLI can save the latest complete service response after every transition:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --state-file /tmp/change-address-state.json \
  --max-interactions 1 \
  change-driving-licence-address
```

It can later use that response as the starting point for its own loop:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --resume /tmp/change-address-state.json
```

The executor itself does not require persistence. The latest complete service response
contains the interaction, continuation token and next advertised action needed by a
consumer to submit the next result. The current mock server signs continuation tokens
with a process-level key, so a saved response remains usable only while the same
mock-server process is available.

## Consumer boundaries

The components have deliberately narrow responsibilities:

- `JourneyClient` handles catalogue discovery and HTTP requests;
- `JourneyExecutor` validates and advances one service response at a time;
- `JsonCliInputProvider` collects manual JSON input for the developer CLI;
- `JsonlTraceRecorder` appends local raw trace events without controlling execution;
- `cli.py` owns the synchronous command-line loop;
- future web, agent and evaluation consumers can call `start()` and `submit()` directly.

This keeps the executor independent of Strands, SvelteKit and any particular rendering,
conversation or evaluation framework.
