# Server-driven journey executor

This package contains a minimal proof-of-concept executor for testing server-driven service journeys on the [Flex Mock API Server](https://github.com/govuk-once/stub-flex-legibility) using protcol 2.0. It discovers an advertised journey, presents each interaction to an input provider, submits the resulting data to the next operation returned by the service, and stops when no further action is available. Its purpose is to demonstrate that a journey can be completed predictably without the client encoding the workflow graph or branching rules; it is not a user-facing interface, an agent implementation, or a production workflow service.

The service, rather than the executor, owns journey progression. The executor:

1. retrieves the journey catalogue;
2. starts an advertised journey;
3. presents the returned `interaction` through an injected input provider;
4. submits the resulting JSON object to the advertised `next_action`, carrying the
   latest `continuation_token`;
5. repeats until the response does not contain `next_action`.

It does not branch on journey status, step identifiers or domain values and does not
load or interpret a workflow graph.

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

Set `USE_STUB_SERVER=1` in `agents/.env`. The CLI loads that file automatically
and retrieves the base URL from the existing `/flex-mock/server-url` Parameter
Store entry:

```sh
uv run python -m agents.src.workflow_executor.cli \
  change-driving-licence-address
```

`STUB_SERVER_URL` can be used as a direct environment-variable override. Values
already present in the process environment take precedence over `agents/.env`.

## Suspend and resume

Save the latest complete response after every transition:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --state-file /tmp/change-address-state.json \
  --max-interactions 1 \
  change-driving-licence-address
```

Resume from that response:

```sh
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --resume /tmp/change-address-state.json
```

The current mock server signs continuation tokens with a process-level key, so a saved
journey can only be resumed while the same mock-server process remains available.

## Future integrations

A web interface, chat system or agent can implement the `InputProvider` protocol. The
executor core does not depend on Strands and does not decide how an interaction is
rendered.

## How execution works

The executor follows a server-driven journey rather than loading or interpreting the complete workflow graph itself.

The main execution loop is implemented in:

```text
agents/src/workflow_executor/executor.py
```

`JourneyExecutor.run()` starts the selected journey, then passes the first response to `JourneyExecutor.continue_from()`.

The executor treats a response as non-terminal when it contains a `next_action` - essentially:

```python
while "next_action" in current:
    action = current["next_action"]
    interaction = current["interaction"]
    continuation_token = current["continuation_token"]

    result = input_provider.collect(interaction)

    current = client.call_action(
        action,
        continuation_token,
        result,
    )
```

For each interaction, the executor:

1. reads the semantic content and input schema returned by the service;
2. passes the interaction to the configured input provider;
3. collects a result conforming to the supplied schema;
4. carries forward the latest continuation token;
5. submits the result to the HTTP operation advertised in `next_action`;
6. replaces the current response with the service’s next response.

The loop stops when the service returns a response without `next_action`.

The executor does not branch on journey-specific details such as:

* status names;
* step identifiers;
* postcode or manual-entry choices;
* confirmation states;
* subsequent endpoint paths.

The service remains authoritative about journey progression. The executor only understands the shared protocol: `interaction`, `continuation_token`, `next_action`, and terminality through the absence of a next action.

HTTP discovery and requests are handled in:

```text
agents/src/workflow_executor/client.py
```

The client retrieves the journey catalogue, finds the advertised start operation, and follows each subsequent operation returned by the service.

## Logging and saving journey responses

The executor accepts an optional `on_response` callback. This is called whenever the executor receives a response from the journey service, including the initial response and every subsequent response returned after submitting an interaction.

```python
if on_response is not None:
    on_response(current)
```

The callback observes the response but does not influence journey progression. It can be used for:

* logging and tracing;
* recording evaluation data;
* saving progress for later resumption;
* updating an external session or state store.

The CLI uses this mechanism when a state file is supplied:

```bash
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --state-file journey-state.json \
  change-driving-licence-address
```

After each service response, the latest response is written to `journey-state.json`. A non-terminal response contains the current interaction, latest continuation token and next advertised action, so it contains everything the executor needs to continue the journey.

A saved journey can be resumed using:

```bash
uv run python -m agents.src.workflow_executor.cli \
  --base-url http://127.0.0.1:8000 \
  --resume journey-state.json
```

`on_response` is deliberately separate from the input provider: the input provider collects the next result from a user or agent, while `on_response` records the service’s response without changing it.
