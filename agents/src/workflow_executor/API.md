# Journey executor prototype API

This is a thin FastAPI adapter around the stepwise executor. It exists so a SvelteKit
prototype can start a journey, display the current interaction and submit a result
without implementing journey progression.

Active runs are held only in the Python process. Restarting the API clears them. This is
not durable journey storage: the latest response is retained only to carry the
service-issued continuation token between browser requests. Each run writes its raw
journey-service exchanges to `.traces/`.

Start the Flex/DVLA stub on port 8000, then run:

```sh
STUB_SERVER_URL=http://127.0.0.1:8000 just api
```

The adapter listens on `http://127.0.0.1:8001`; its OpenAPI documentation is available
at `/docs`. The SvelteKit development origins on port 5173 are allowed by CORS.

## Operations

Start a run:

```http
POST /api/journey-runs
Content-Type: application/json

{"journey_id": "change-driving-licence-address"}
```

Submit a result for the returned `run_id`:

```http
POST /api/journey-runs/{run_id}/results
Content-Type: application/json

{"result": {"use_postcode_lookup": true}}
```

Inspect the raw trace accumulated so far:

```http
GET /api/journey-runs/{run_id}/trace
```

The run response contains only the current interaction, status and terminality. The
continuation token and advertised next operation remain inside the Python adapter.
