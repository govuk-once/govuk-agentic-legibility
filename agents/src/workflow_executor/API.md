# Journey executor prototype API

This is a thin FastAPI adapter around the stepwise executor. It exists so a SvelteKit
prototype can start a journey, ask for bounded agent assistance, display the current
interaction and submit a reviewed result without implementing journey progression.

Active runs are held only in the Python process. Restarting the API clears them. This is
not durable journey storage: the latest response is retained only to carry the
service-issued continuation token between browser requests. Each run writes its raw
application and journey-service events to `.traces/`.

## Run locally

Start the Flex/DVLA stub on port 8000. Configure a Bedrock model or inference profile in
`agents/.env`:

```dotenv
JOURNEY_AGENT_MODEL_ID=<Bedrock model or inference-profile ID>
JOURNEY_AGENT_REGION=eu-west-2
```

Then run the adapter from a shell with AWS credentials:

```sh
STUB_SERVER_URL=http://127.0.0.1:8000 just api
```

The adapter listens on `http://127.0.0.1:8001`; its OpenAPI documentation is available
at `/docs`. The SvelteKit development origins on port 5173 are allowed by CORS.

The model is optional. Without `JOURNEY_AGENT_MODEL_ID`, the manual form path remains
available but the assistance operation returns HTTP 503.

## Operations

Start a run:

```http
POST /api/journey-runs
Content-Type: application/json

{"journey_id": "change-driving-licence-address"}
```

Ask for a structured proposal for the current interaction:

```http
POST /api/journey-runs/{run_id}/assistance
Content-Type: application/json

{
  "message": "Yes, use my postcode",
  "conversation": []
}
```

This operation does not submit values or advance the journey. It returns
`propose_values` or `no_safe_suggestion`.

Submit the reviewed result:

```http
POST /api/journey-runs/{run_id}/results
Content-Type: application/json

{"result": {"use_postcode_lookup": true}}
```

Inspect the raw trace accumulated so far:

```http
GET /api/journey-runs/{run_id}/trace
```

The trace includes user messages, assistant invocations and structured responses,
proposal review, submitted results, and exact journey-service HTTP exchanges. It does
not record hidden model reasoning.

The run response contains only the current interaction, status and terminality. The
continuation token and advertised next operation remain inside the Python adapter.
