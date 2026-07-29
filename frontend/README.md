# Journey executor frontend

This SvelteKit application is a developer-facing demonstration of the deterministic,
server-driven journey executor. It renders the current interaction from its JSON Schema
and exposes the frontend state, service-selected interaction sequence, and raw JSONL
transport trace alongside the user-facing journey.

It deliberately contains no journey-specific branching. The browser sends a run ID and
the values collected for the current interaction to the Python HTTP adapter. The executor
retains the continuation token and follows the operation advertised by the journey service.

## Run locally

Run the DVLA-like mock service on port 8000, then start the Python adapter:

```bash
STUB_SERVER_URL=http://127.0.0.1:8000 just api
```

Install and start the frontend in another terminal:

```bash
just frontend-install
just frontend
```

Open <http://127.0.0.1:5173>.

The frontend defaults to `http://127.0.0.1:8001`. Override it with
`PUBLIC_JOURNEY_API_URL` when necessary.

## Checks

```bash
just frontend-check
just frontend-build
```

The existing `just check` remains the Python suite. `just check-all` runs the Python and
frontend checks after frontend dependencies have been installed.

## Renderer scope

The prototype supports booleans, strings, string enums, integers, numbers, required-field
checks, and semantic content data used for review summaries. Unsupported schema types are
displayed explicitly instead of being silently ignored.
