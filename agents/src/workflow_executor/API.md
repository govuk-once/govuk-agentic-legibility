# Journey executor prototype API

This is a thin FastAPI adapter around the stepwise executor. It exists so a SvelteKit
prototype, automated fixture runner or another client can start a journey, inspect the
current interaction and submit a reviewed result without implementing journey
progression.

Active runs are held only in the Python process. Restarting the API clears them. Each
run writes raw application and journey-service events to `.traces/`.

## Conversation fixtures

Version-controlled conversation inputs live in `agents/src/evaluation/fixtures/`.
They are ordinary JSON files and are not coupled to the frontend. The same fixture
repository can be used by the HTTP application and future automated evaluation runners.

List available fixtures:

```http
GET /api/conversation-fixtures
```

Start a run with a fixture:

```http
POST /api/journey-runs
Content-Type: application/json

{
  "journey_id": "change-driving-licence-address",
  "fixture_id": "complete-address-postcode-lookup"
}
```

The backend stores the fixed source conversation with the run and asks the interaction
assistant for suggestions automatically at every non-terminal interaction. A client does
not need to request suggestions explicitly.

Start without a fixture by omitting `fixture_id` or setting it to `null`. The journey
remains manually executable.

## Add information during a run

A user can add a correction or clarification without advancing the journey:

```http
POST /api/journey-runs/{run_id}/messages
Content-Type: application/json

{
  "content": "Sorry, the building number is 81, not 18."
}
```

The backend appends the user message to the run conversation and refreshes suggestions
for the current interaction. Agent proposals are not inserted into the conversation.
They remain application events in the raw trace.

## Submit the reviewed result

```http
POST /api/journey-runs/{run_id}/results
Content-Type: application/json

{"result": {"use_postcode_lookup": true}}
```

The run response includes:

- the current interaction and terminality;
- the selected fixture and complete user-visible conversation;
- the latest structured assistance action or assistance error.

The continuation token and advertised next operation remain inside the Python adapter.

## Inspect the raw trace

```http
GET /api/journey-runs/{run_id}/trace
```

The trace includes the fixture ID, version and source-file hash, complete assistant
inputs, structured assistant responses, proposal review, submitted results and exact
journey-service HTTP exchanges. It does not record hidden model reasoning.
