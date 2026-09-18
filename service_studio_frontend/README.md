# Service Studio

Service Studio is an experimental prototype for the frontend work on the canonical service schema. It shows how a service is onboarded to the tool, and how a service graph is created, edited and saved.

It is early development.

## Prerequisites

* A current version of Node
* pnpm

## Dependencies

Beyond SvelteKit itself, the app has two dependencies:

* `zod` is the validation library the canonical service schema is written with, and what every check against it runs through.
* `@dagrejs/dagre` lays out the graph editor's canvas: it works out which rank each node belongs to and where it sits, the app only converts that into on screen positions.

The onboard route also depends on `@anthropic-ai/bedrock-sdk` and `@anthropic-ai/sdk`, to call Claude Sonnet 5 on Amazon Bedrock, see the Onboard section below.

## Install

```sh
pnpm install
```

## Run

Start the development server:

```sh
pnpm run dev
```

Open the local address shown in the terminal.

## Checks

```sh
pnpm run check
pnpm test
```

`pnpm run check` runs the type and Svelte checks. `pnpm test` runs the unit tests with Vitest.

## Routes

`/edit` is the service selection: choose an example service, then open its graph editor.

`/edit/[slug]` is the visual journey graph editor for one chosen service.

`/onboard` is the onboarding of a service journey.

### Onboard
This route is where the onboarding process for services is developed. `/onboard/details` collects a service name, description and links to the service, then calls Claude Sonnet 5 on Amazon Bedrock to draft a canonical schema. Every link is fetched by the server first in this early iteration, and the result is validated against the same schema as everywhere else in the app before it is shown. This method will be updated to use AWS Agent Core next to access better tool calls for this. The document upload field is not wired in yet. `/onboard/draft` shows the result and lets you download the JSON, to add to `src/lib/examples` by hand for now. It is a separate route so its design can move ahead without touching the editor. The download step goes away once onboarding and the editor are joined up.

The API call needs two environment variables, copy `.env.example` to `.env` and fill them in:
* `AWS_BEARER_TOKEN_BEDROCK`, a bearer token for Amazon Bedrock
* `AWS_REGION`, the Bedrock region to call, `eu-west-2` by default

Claude Sonnet 5 on Bedrock has to be called through a cross-region inference profile id, `eu.anthropic.claude-sonnet-5`, which keeps requests inside the EU rather than routing globally (see `src/lib/server/onboard/client.ts`). This current implementation of Bedrock's endpoints for this model do not accept `output_config`, so the response shape is not enforced by Bedrock itself: the canonical schema is instead given to Claude as JSON Schema inside the system prompt (`src/lib/server/onboard/system-prompt.ts`, built from the same Zod schema with `toJSONSchema`), and the reply is validated the normal way with `parseService` once it comes back. This should be updated to use Agent Core structured output tooling in the next iteration after this initial proof of concept.

### Graph editor
`/edit` is a service selection: choose a service from the dropdown, see its step and branch counts, then open the graph editor. A file that does not match the canonical schema is still listed, but shows its validation problems in place of the stats and the open button.

`/edit/[slug]` is the editor itself, a full canvas graph editor page. Each step is a box, a step with more than one onward route gets a plain condition diamond, and the start and end of the journey are solid circles. Selecting a step, in the list or on the canvas, highlights it in both places, and clicking a step on the canvas opens it for editing directly.

A left hand tool rail, Step, Condition, Start, End, is click to arm, then click a step on the canvas to apply it: Condition adds a branch route to a step, Start moves the journey's entry point, End clears a step's onward routes, removing anything that is left unreachable as a result, and Step, like the "+" that appears on any route out of a step, inserts a new step onto that one route, splicing it in between and leaving the step's other routes, if it has any, untouched. A branch route's own label and condition are edited in the step editor once it is open, not drawn on the canvas itself. "Show branching" collapses every branch down to its first route, for a simpler read of a long journey, without changing the underlying service. The minimap and the Fit and zoom controls in the header track the same canvas.

Next iterations will be to implement a more intuative drag and drop of graph components onto the canvas.

To add an example, drop a JSON file into `src/lib/examples`. It must match the canonical schema exactly, so fix the source of a service definition rather than relying on the tool to work around it. A file that does not match is still listed in the picker's dropdown, but shows its validation problems in place of a graph.

## Key files

### Schema, `src/lib/schema/`
* `service.ts` is the canonical service schema written as Zod, transcribed from the RFC, with a  comment detailing any difference from the original RFC. It also exports the `Service` and `ServiceStep` types the rest of the app uses.
* `validate.ts` exports `parseService`, which validates a file against the canonical schema and returns either the typed service or a flat list of problems for an error summary.
* `step-kind.ts` holds the label and tag colour for each step kind, and `defaultStepType`, which returns the smallest valid type object for a kind. The editor uses it when a step's type is changed.

### Examples, `src/lib/examples/`
* `index.ts` loads every `.json` file in the folder at build time, validates each one, and sorts them smallest first for the dropdown.
* `change-driving-licence-address.json` and `report-a-change-that-affects-your-benefits.json` are small hand written examples that between them cover a branch, a condition and every step kind.
* `maternity-allowance-online.json` is a large real example, 61 steps, converted from the DWP Maternity Allowance private beta journey.

### Graph, `src/lib/graph/`
* `service-to-graph.ts` turns a validated service into the nodes and edges the graph draws. It adds the start and end circles, and a plain decision diamond, with no text of its own, for any step with more than one route.
* `layout.ts` places the nodes top to bottom in ranks. It hands the ranking, ordering and cycle handling to `@dagrejs/dagre`, our only other dependency besides Zod, converts its output into the positions the renderer expects, and reorders a branch's own siblings left to right to match their step numbers, which dagre's own layout does not consider.
* `node-sizing.ts` works out how wide and tall each step box needs to be for its own text.
* `types.ts` holds the node and edge types shared by the builder, the layout and the components.
* `JourneyGraph.svelte` is the renderer: HTML boxes over one SVG edge layer, inside a pannable and zoomable viewport. It fits the graph to the canvas on load and again whenever the service changes.
* `GraphToolbar.svelte` is the left hand tool rail, Step, Condition, Start and End, click to arm.
* `GraphMinimap.svelte` is the small overview in the corner of the canvas, with a draggable viewport rectangle.
* `StepNode.svelte`, `ConditionNode.svelte` and `TerminalNode.svelte` are the three node shapes: rectangle, diamond, circle.

### Editor page
* `src/routes/edit/+page.svelte` is the service selection: it chooses which example service to open, nothing else.
* `src/routes/edit/[slug]/+page.ts` resolves the service named in the URL against the bundled examples, and returns a 404 if it does not match one.
* `src/routes/edit/[slug]/+page.svelte` owns the working copy of the chosen service and every edit handler, and renders the tool rail, the canvas and the right hand panel, either the step list or a single step's editor.
* `src/lib/components/StepCard.svelte` is a step row in the list.
* `src/lib/components/StepEditorCard.svelte` is the open editor for one step: its name, description, type, onward routes, and, for a branch, each route's own label.

## Next steps

* A more intuative drag, drop, connect for the graph editor.
* A fuller step editor covering fields, conditions and the endpoint call contract
* Join the editor up with the onboarding route once its design is settled
