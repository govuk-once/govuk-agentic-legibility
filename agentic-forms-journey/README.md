# Agentic Forms Journey

This demo web app builds upon an earlier [Agentic-forms proof of concept by Maxwell Riess.](https://github.com/MaxwellRiess/Agentic-forms-poc)

This earlier iteration explored how GOV.UK Forms could be made ligible to AI Agents. This poc took an exported GOV.UK Form in its JSON format and mapped this deterministically to a schema. A deterministically coded agent then executed the form.

The areas brought formward into this repo and referenced in the code are:
- `contract-builder.ts` `slugify()`, `answerFragment()` and `buildAgentContract()` .
- `deterministic.ts`
- `validate.ts` and the use of `Ajv library`

This repo is the next iteration that takes a GOV.UK Forms export, uses an API call to Anthropic to let an LLM agent complete the form through a probalistic real-time chat interface, and shows a step by step breakdown of how the agent worked through it in a journey map.

Upload the JSON export of a form built on [GOV.UK Forms](https://www.forms.service.gov.uk/), tell the LLM in plain language what you need (for example "Report a pothole on my street"), and the agent fills in everything it can work out on its own. It only asks you for the details it cannot find or was not given. This iteration explores what can be inferred from as little information as possible. For example, can an address be filled out from just a postcode.

Alongside the chat, the app runs the  determinstic pass from the original poc over the same form and compares the two. This makes it easier to see what the 'live' agent inferred, which questions it answered, where a branch condition in the form was taken. This can help future discussions around where a human should still check the result before trusting it.

It now also has a run log and a compare page: a run can be recorded against a set of criteria, and different methods can be measured against each other. See [Update: run log and compare](#update-run-log-and-compare) below.

## What the project does

There are two runs over every uploaded form:

- **LLM run.** The agent reads the whole conversation, fills the fields it can, and replies to you. This is the conversational path.
- **Deterministic run.** A fixed baseline that fills every required field with placeholder values. It always completes, so it acts as a reference point to compare the agent against. This is carried over from the first poc.

Both runs pass through the same five stages: discover, understand, fill, validate, and submit. The results page shows each run stage by stage, plus a comparison, the branch conditions in the form, and a full journey flow from the first question to the last.

The submit stage is simulated. Nothing is sent to a real government service. A successful submit returns a made up reference so you can see the outcome in the interface.

### Update: run log and compare

Two newer pages let you keep a record of a run and measure methods against each other:

- **Run log** (`/log`). Records the latest agent run against four things: time and tokens, the full conversation, what the agent did to each field, and a reserved slot for journey executor actions that other prototypes have in their trace (this demo has no executor). You can name the run and export it as a JSON file, so every method has a portable record.
**Next steps are to align the log with the common trace in the RFC for other prototypes.**
- **Compare** (`/compare`). Loads several run logs and puts them side by side: a scorecard, an at a glance chart, and a question by question view of where the methods differ. Only methods that ran the same form are compared, so it stays like for like. It includes example methods to try, and can generate simple "verbose" (like a form filling step by step process) and "aggressive" (fully autonomous) versions from one real run so a single log still has something to compare against. ideally you would compare against variations of the same form but different user inputs.

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
| `src/routes/log/+page.svelte` | The `/log` page: one run's four criteria, plus JSON export. |
| `src/routes/compare/+page.svelte` | The `/compare` page: run logs side by side (scorecard, chart, divergence). |
| `src/lib/run-log.ts` | The portable run log format (types and Zod schema) shared by both pages. |
| `src/lib/compare-metrics.ts` | Scorecard and divergence calculations for the compare page. |
| `src/lib/variants.ts` | Generates synthetic comparator methods from a real run. |
| `src/lib/fixtures.ts` | Example run logs used by the compare page. |
| `src/lib/schemas.ts` | Zod schemas for the uploaded form, the agent's output, and the journey stages. |
| `src/lib/server/contract-builder.ts` | Builds the shared mapping, JSON Schema, and branching rules from a form. |
| `src/lib/server/llm.ts` | Talks to the Anthropic Messages API and returns the agent's answers and reply. |
| `src/lib/server/deterministic.ts` | The fixed baseline run (hard coded agent) from the original poc. |
| `src/lib/server/journey-runner.ts` | Runs one journey through all five stages. |
| `src/lib/server/validation.ts` | Ajv validation of answers against the generated schema. |
| `src/lib/server/flow.ts` | Annotates each question with the agent run's outcome for the journey flow. |
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

