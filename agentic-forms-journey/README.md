# Agentic Forms Journey

This demo web app builds upon an earlier [Agentic-forms proof of concept by Maxwell Riess.](https://github.com/MaxwellRiess/Agentic-forms-poc)

This earlier iteration explored how GOV.UK Forms could be made ligible to AI Agents. This poc took an exported GOV.UK Form in its JSON format and mapped this deterministically to a schema. A deterministically coded agent then executed the form.

The areas brought forward into this repo and referenced in the code are:
- `contract-builder.ts` `slugify()`, `answerFragment()` and `buildAgentContract()` .
- `deterministic.ts`
- `validate.ts` and the use of `Ajv library`

This repo is the next iteration that takes a GOV.UK Forms export, uses an API call to Anthropic to let an LLM agent complete the form through a probalistic real-time chat interface, and shows a step by step breakdown of how the agent worked through it in a journey map.

Upload the JSON export of a form built on [GOV.UK Forms](https://www.forms.service.gov.uk/), tell the LLM in plain language what you need (for example "Report a pothole on my street"), and the agent fills in everything it can work out on its own. It only asks you for the details it cannot find or was not given. This iteration explores what can be inferred from as little information as possible. For example, can an address be filled out from just a postcode.

Alongside the chat, the app runs the  determinstic pass from the original poc over the same form and compares the two. This makes it easier to see what the 'live' agent inferred, which questions it answered, where a branch condition in the form was taken. This can help future discussions around where a human should still check the result before trusting it.

It now also has a run log and a compare page: a run can be recorded as a common trace, a shared event format agreed with other teams building similar prototypes, so different methods can be measured against each other on the same terms. See [Update: run log and compare](#update-run-log-and-compare) below.

## What the project does

There are two runs over every uploaded form:

- **LLM run.** The agent reads the whole conversation, fills the fields it can, and replies to you. This is the conversational path.
- **Deterministic run.** A fixed baseline that fills every required field with placeholder values. It always completes, so it acts as a reference point to compare the agent against. This is carried over from the first poc.

Both runs pass through the same five stages: discover, understand, fill, validate, and submit. The results page shows each run stage by stage, plus a comparison, the branch conditions in the form, and a full journey flow from the first question to the last.

The submit stage is simulated. Nothing is sent to a real government service. A successful submit returns a made up reference so you can see the outcome in the interface.

### Update: run log and compare

Two newer pages let you keep a portable record of a run and measure methods against each other, using a shared event format called the **common trace**.

A common trace is a small record of what happened during a run: which questions became available, what values were proposed and submitted, and how the run ended. It is agreed with the other teams building similar prototypes, so a run from this app can be compared against theirs on the same terms. It deliberately leaves out the exact wording of the conversation. This prototype keeps that detail in a separate raw trace (`src/lib/raw-trace.ts`), which the common trace's `source_trace` field points to.

- **Run log** (`/log`). Builds a common trace live as the agent runs, turn by turn, and lets you export it, and the full raw trace behind it, as JSON.
- **Compare** (`/compare`). Loads several common traces and puts them side by side: an event-count scorecard (how many values were proposed, submitted, and so on), and a question by question view of what each method actually submitted. Only methods that ran the same journey are compared, so it stays like for like. It includes example methods to try, and can generate synthetic comparators from one real trace so a single loaded trace still has something to compare against.

## Main runtime surfaces

- **Home page** (`src/routes/+page.svelte`). The whole interface: the file upload, the chat, and the results breakdown. The uploaded form and the conversation live in the browser and are sent to the server on each turn.
- **Run endpoint** (`src/routes/api/run/+server.ts`). A single `POST /api/run` route. It takes the uploaded form JSON and the conversation so far, runs both passes, and returns the comparison plus the agent's reply.

## Prerequisites

- **Node.js 20 or newer.** Version 20 was used during development.
- **pnpm.** The lockfile and workspace file are for pnpm. Version 10 was used during development.
- **An Anthropic API key.** The agent calls the Anthropic Messages API directly. Without a key the chat cannot run, though the app still loads.

## Environment variables

Copy `.env.example` to `.env` and fill in your key:

```sh
cp .env.example .env
```

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | none | Authenticates calls to the Anthropic Messages API. The chat fails clearly if it is missing. |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-5` | Which model the agent uses. |

The key is read on the server only (through SvelteKit's private environment). It is never sent to the browser.

## Local development

Install dependencies and start the development server:

```sh
pnpm install
pnpm dev
```

To open the app in a new browser tab automatically:

```sh
pnpm dev -- --open
```

Then upload a GOV.UK Forms JSON export and start chatting with the agent.

## Checking the code

Run the type and Svelte checks:

```sh
pnpm check
```

This syncs the generated SvelteKit types and runs `svelte-check`. There is no test suite or linter set up yet.


## Key processes and pages

The server side logic lives in `src/lib/server`. A single request flows through it like this:

1. **Validate the upload.** `schemas.ts` uses Zod to check the uploaded form is a shape the app understands before anything else runs.
2. **Build the contract.** `contract-builder.ts` turns the form into one shared package of information: a stable key per question, a JSON Schema describing valid answers, and a list of branching rules. Both runs use this same contract so the comparison stays fair.
3. **Run the deterministic baseline.** `deterministic.ts` fills every required field with fixed placeholder values.
4. **Run the agent.** `llm.ts` sends the conversation and the form context to the Anthropic Messages API. It forces a tool call so the model always returns structured answers plus a natural reply. The tool schema is built from the form's own fields, which guides the model to put each value in the right place.
5. **Score each run.** `journey-runner.ts` walks both sets of answers through the five stages. `validation.ts` checks the answers against the generated JSON Schema using Ajv.
6. **Explain the result.** `flow.ts` and `branch-trace.ts` work out, question by question, whether each one was answered, skipped by a branch, or still needs a human to confirm the route. `compare.ts` gathers everything into the response the page renders.

## Directory map

| Path | What lives there |
| --- | --- |
| `src/routes/+page.svelte` | The full user interface: upload, chat, and results. |
| `src/routes/api/run/+server.ts` | The `POST /api/run` endpoint that drives one agent turn. |
| `src/routes/log/+page.svelte` | The `/log` page: the current run's common trace, event by event, plus JSON export. |
| `src/routes/compare/+page.svelte` | The `/compare` page: common traces side by side (scorecard, chart, divergence). |
| `src/lib/common-trace.ts` | The common trace format: the shared event types, and the Zod schema used to validate an imported trace. |
| `src/lib/trace-builder.ts` | Turns the running conversation into a common trace, turn by turn. |
| `src/lib/raw-trace.ts` | The full detail behind one run: the raw trace a common trace's `source_trace` field points to. |
| `src/lib/trace-display.ts` | Shared formatting for common trace events (labels, tag colours, value text), used by `/log` and `/compare`. |
| `src/lib/stores/trace.svelte.ts` | Reactive store holding the current run's common trace and raw trace, so `/log` still shows them after navigating there. |
| `src/lib/compare-metrics.ts` | Journey grouping, scorecard, and divergence calculations for the compare page. |
| `src/lib/variants.ts` | Generates synthetic comparator methods from a real trace. |
| `src/lib/fixtures.ts` | Example common traces used by the compare page. |
| `src/lib/schemas.ts` | Zod schemas for the uploaded form, the agent's output, and the journey stages. |
| `src/lib/flow.ts` | Annotates each question with a run's outcome for the journey flow. Used by both the server pipeline and the browser-side trace builder, so it lives outside `server/`. |
| `src/lib/server/contract-builder.ts` | Builds the shared mapping, JSON Schema, and branching rules from a form. |
| `src/lib/server/llm.ts` | Talks to the Anthropic Messages API and returns the agent's answers and reply. |
| `src/lib/server/deterministic.ts` | The fixed baseline run (hard coded agent) from the original poc. |
| `src/lib/server/journey-runner.ts` | Runs one journey through all five stages. |
| `src/lib/server/validation.ts` | Ajv validation of answers against the generated schema. |
| `src/lib/server/branch-trace.ts` | Builds one trace row per routing rule. |
| `src/lib/server/compare.ts` | Ties the two runs together into the comparison response. |
| `src/lib/server/engine-types.ts` | Shared TypeScript types for the server pipeline. |
| `static/gov.css`, `static/govuk-extras.css`, `static/fonts` | GOV.UK styling and fonts used by the interface. |

## Known limitations and follow up

- **The submit stage is simulated.** No form is sent to any real service. See `journey-runner.ts`.
- **File answer types cannot be filled automatically.** A form question that expects a file upload is flagged as needing a human. See `deterministic.ts`.
- **No tests or linter yet.** `pnpm check` covers types and Svelte checks only.

### Authors and Support
This project was made by Alex and Jen at Considerate Digital. If you need support please [contact us](https://considerate.digital).

