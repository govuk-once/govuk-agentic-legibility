# Service Studio

Service Studio is a prototype for drafting, editing and reviewing government services as visual journey graphs that also create a canonical schema in the background. A draft can be written by an LLM assistant from a short description and public links to GOV.UK information, or started from an existing GOV.UK form example. It is then edited on a visual canvas and checked before it goes on to the next review. The canonical schema is generated and updated when edited in the visual graph editor. In order to proceed to the review stages the schema must pass a validation check.

The forms route is the minimum viable product (MVP) with a simp;ified set of states used in the canonical schema and is being user tested. The service routes included experimental additions and more comprehensive canonical schema states to account for more complex steps in a journey.

The user testing of the MVP will inform design decisions in the more complex unified schema representation for service routes.

## Prerequisites

* A current version of Node
* pnpm
* An Amazon Bedrock Anthropic API key, only needed to generate a draft with the assistant. Bedrock keys made in the AWS console often expire after a few hours, so a new key may be needed for each session.

The main libraries, which `pnpm install` adds:

* `zod` writes the schema of a workflow, and every validation check of a file against the schema runs through it.
* `@xyflow/svelte` (Svelte Flow) is the canvas. It draws the boxes and lines, and handles panning, zooming, dragging and drawing lines.
* `@dagrejs/dagre` works out where each box sits when the graph is arranged.
* `@anthropic-ai/bedrock-sdk` and `@anthropic-ai/sdk` call Claude on Amazon Bedrock to write a draft. In a next iteration the draft generation will be updated to use AWS Agent Core and this may change.

## Install

```sh
pnpm install
```

To generate drafts, copy `.env.example` to `.env` and fill in:

* `AWS_BEARER_TOKEN_BEDROCK`, the Bedrock key
* `AWS_REGION`, the Bedrock region, `eu-west-2` by default

## Run

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

### Forms

* `/` opens the start page, `/onboard`. Start a new form from here. Starting a new service is inactive for now. However, the routes can be reached by manually typing the local urls.
* `/onboard/form/method` asks how to draft the form: with the assistant, or from an existing GOV.UK form. Starting with a blank graph is not available yet.
* `/onboard/form/details` takes a name, a description and links, and generates a first draft.
* `/onboard/form/draft` shows the draft, with how many steps and branches it has. It also displays any errors that occur at generation and suggest re-running if it fails validation. Edit opens it in the form editor.
* `/edit-form` lists the example forms. Choose one to open it.
* `/edit-form/[slug]` is the form editor for one example form.
* `/edit-form/draft` is the form editor for the generated draft.
After editing, a form goes through three stages: the owner review, the technical review, then sign off. The owner adds their details first, a developer then sets up the technical side, and the owner comes back to sign off. The owner and the developer would be different people working at different times. For now the whole order runs in one browser tab, so it can be tried from start to finish.

* `/owner-review/form` is the owner review, in three steps with an address each, so the back button works and a step can be linked to:
  * `/owner-review/form` takes the owner's name, department and email, and optional context for the agent. These are written into the workflow manifest.
  * `/owner-review/form/review` shows the technical review, the validation checks and the citizen journey. Before the technical review it shows the review as not finished and continues to it. Afterwards the banner shows Sign off, and the page continues to sign off. The technical review counts as finished when every API call is connected and every developer step holds the time a technical review was sent. The validation checks are not real yet, so a "Show example problems" tick box switches between a form with problems and one that is all clear.
  * `/owner-review/form/sign-off` lists what must be done before publishing. Each item turns green when its part of the review is done.
* `/tech-review/form` is the technical review. A developer sets up the technical side of the form in four steps, each with its own address:
  * `/tech-review/form` sets the workflow settings: how long one run may last, and the time limit and tries every API call uses unless it sets its own. These are written into the workflow manifest.
  * `/tech-review/form/flex` lists the API call steps and whether each is connected to a Flex endpoint. `/tech-review/form/flex/[step]` finds an endpoint for one step and writes its method, service, url and body fields into the step. The endpoints are made up examples until the real Flex list is ready, and search and filters are inactive.
  * `/tech-review/form/step-values` lists the developer steps (API calls, assign steps and waits). Each opens a panel where its values are checked and changed, then marked as checked. Which steps are checked is kept while the browser tab stays on Service Studio.
  * `/tech-review/form/review` sums up the review. Send for sign off writes the time it was sent into each developer step, as `tech_review_checked_at` in its metadata, and goes back to the owner review.
* `/owner-review/form/published` confirms the form is published. Publishing does not send or save the form yet.

The form is carried from the editor to the reviews in the browser tab, in the same way as a generated draft. The technical review writes its changes back into that copy. Review pages opened without it say there is nothing to review.

### Services, experimental

* `/onboard/service/method`, `/onboard/service/details` and `/onboard/service/draft` draft a service in the same way as a form.
* `/edit-service` and `/edit-service/[slug]` open an example service, and `/edit-service/draft` opens a generated one.

## Using the form editor

The canvas is on the left and a panel of ordered steps is on the right.

* **Adding shapes.** Drag a Question, Message, Decision, Start or End from the palette onto the canvas. A question or a message is added to the form straight away. A decision, start or end is drawn dotted until it is joined up, and then becomes part of the form.
* **Drawing lines.** Drag from the dot on the edge of a shape to another shape. Letting go on empty canvas adds a new question there, already joined. A second line from a step puts a decision after it.
* **Editing.** Selecting a node on the canvas or 'edit' in a numbered step in the panel, opens its card in the panel. A question or a message has its words, title, description and hint. A decision names each way out by the answer that leads to it, with where it goes. A developer state, such as the assign that saves a repeated answer, is shown but not editedable in this view (it would happen later in tech-review).
* **Moving and removing.** The arrows on a card in the list move a step up or down the journey, and the graph is arranged again to match. Removing takes out only what was chosen. Nothing is joined up for you, so the pieces left over show what still needs joining.
* **Where boxes sit.** The graph is arranged when it is opened, when developer states are shown or hidden, and after a move. Otherwise every box keeps its place, and a new shape stays where it was drawn.
* **Send to owner review** checks the form. Validation errors and warning are listed in the panel, and choosing one highlights its box on the canvas. A form with nothing to fix goes on to the owner review.

## Shared parts, forms and services

Forms and services use the same schema, canvas and onboarding code, and each has its own editor and routes. Either can run without the other and therefore can be deleted after user testing or merged if more applicable further down the design iteration process.

Shared by both:

* `src/lib/schema/workflow/`, the schema and every change the editors make to a journey
* `src/lib/process-graph/` and `src/lib/graph-kit/`, the canvas, the shapes and the layout
* `src/lib/components/`, the page header, progress bar and onboarding pages
* `src/lib/server/shared/`, reading links, asking the model and wrapping its reply into a workflow
* `src/lib/draft-store.ts` and `src/lib/examples/`

Forms only:

* `src/lib/form-editor/`, `src/lib/server/onboard-form/`
* `src/routes/edit-form/`, `src/routes/onboard/form/`, `src/routes/tech-review/form/`, `src/routes/owner-review/form/`

Services only:

* `src/lib/service-editor/`, `src/lib/server/onboard-service/`
* `src/routes/edit-service/`, `src/routes/onboard/service/`

A test, `src/lib/tests/folder-boundaries.test.ts`, keeps these apart. It fails if a form file imports from a service file, or the other way round, or if a shared file imports from either. So the services can be removed without breaking forms, and forms can be user tested while the services stay experimental.

## Validation

Validation checks happen at set points, but not while a journey is being composed and edited in the graph editor. This allows more flexibility for a non-technical user to compose new flows without the friction of either auto routing mid composition or lots of validation errors whilst halfway through a composition. For a beginner user this is determined as a better approach but it may change once users become more familiar with the interface.

* **The shape of a file.** The Zod schemas in `src/lib/schema/workflow/` describe every key of a workflow manifest, a process and each kind of state. `process.ts` and `workflow.ts` are the top of each.
* **Checks across a whole file.** `src/lib/schema/workflow/validate.ts` checks what one state cannot see on its own: that every route leads to a state that exists, that the start exists, that a process has an end, and that the manifest and its processes agree. `parseProcess` and `parseWorkflow` run the schema and these checks together.
* **Loading the examples.** `src/lib/examples/workflows.ts` checks every example as it is loaded. An example that fails is still listed, with its problems in place of the open button.
* **A draft from the model.** `src/lib/server/shared/generate-workflow.ts` checks the reply as a process, then wraps it and checks the whole workflow. A form is also refused if it has a state a form cannot have, such as an API call or invoke state(`src/lib/server/onboard-form/build-form.ts`). Any problems are sent back to the model once to be corrected (`src/lib/server/shared/generate-json.ts`). As more user testing occurs more states may be allowed in the forms MVP validation process. However, currently it is limited to input, output, end and choice.An existing GOV.UK form example can also contain an assign state but it is not autogenerated for now.
* **Opening a draft in an editor.** `src/lib/draft-store.ts` checks the draft again when it is read from the browser tab, because it could have changed there. The form editor also checks that a workflow is a single process (`src/lib/form-editor/schema/form-states.ts`).
* **While editing.** Nothing is checked. A step may have nothing after it, a decision may have a way out that leads nowhere, and pieces may be loose. The editor holds a journey in a looser shape for this, in `src/lib/schema/workflow/working-process.ts`.
* **Before the reviews.** `journeyErrors` in `validate.ts` lists what must be fixed, in plain words, naming each step as the editor does. `journeyWarnings` lists placeholder text still to replace, which does not stop the form going on. Placeholders that a later review fills in, such as the owner and contact, are not listed. The form editor shows both lists in `src/lib/form-editor/components/JourneyCheckPanel.svelte`.
* **At tech review.** Each step of the technical review checks what is typed before it is written into the form: the workflow settings in `src/lib/schema/workflow/workflow-settings.ts`, and the values of each developer step in `src/lib/form-editor/step-values/`. A body field still holding the placeholder a connected endpoint left for it stops the step being marked as checked.
* **At owner review.** `ownerDetailsProblems` in `src/lib/schema/workflow/owner-details.ts` checks the owner's details before they are written into the manifest. The names, department and email are required, and the email must be a valid address.

## Generating a draft

The details page posts a name, a description and links to the draft page's form action. On the server:

1. The page behind each link is read, if it is on GOV.UK (`src/lib/server/shared/read-links.ts`, `src/lib/server/shared/fetch-link.ts`, `src/lib/server/shared/allowed-link-domains.ts`).
2. The LLM is asked for one process, with the prompt for that route. The form prompt is `src/lib/server/onboard-form/system-prompt.ts` and the service prompt is `src/lib/server/onboard-service/system-prompt.ts`. Each ends with the JSON Schema of a process, made from the Zod schema, because Bedrock does not enforce the shape of the reply for this model. This will be updated to use Agent Core tool calls to improve this in a later version before deployment.
3. The process is wrapped into a workflow with placeholders for what the model is not asked for, such as the owner, contact and executor settings (`src/lib/server/shared/build-draft-workflow.ts`). A form keeps its name as the manifest description, and the description typed on the details page in the manifest metadata.

The draft is then held in the browser tab so the editor page can open it. It is not saved anywhere.

## Project layout

```
src/
  lib/
    schema/workflow/   the schema, the checks, and the changes made to a journey
    process-graph/     the shared canvas, drafts, layout and lists of steps
    graph-kit/         the box, diamond and dot shapes, the palette and sizing
    components/        shared page parts and onboarding pages
    form-editor/       the form editor
    service-editor/    the service editor
    server/            onboarding on the server: shared, form and service
    examples/          the example forms and services, as JSON files
    tests/             tests that cover the whole project
  routes/              the pages, as listed above
static/                gov.css and govuk-extras.css
```

Tests sit in a `tests` folder beside the code they test.

Every folder ending in `-old` (`components-old`, `graph-old`, `schema-old`, `examples/old`, `server/onboard-old`, `routes/edit-old`, `routes/onboard-old`) will be deleted. They stay for now as a reference for the design of the old editor.

## Next steps

* Give the owner review its real validation checks in place of the example problems.
* Connect the Flex connections to the real Flex list, or to mock APIs, in `src/lib/flex/`, and make search and filters work.
* Check that every saved answer a step reads, such as a body value, is saved by some step in the form.
* Make Publish save the form as its two files, the manifest and the process. This will later be replaced by sending it to the workflow server. It will only be allowed when the validation check passes.
* Make "Save for later", "Open step in editor", "Go to service dashboard" and "View the published journey" work. They are shown but inactive for now.
* Re-design the "Continues to" dropdown list UI on the edit card, which lists every state and is long on large forms. Change to another approach.
* Choose an answer type for a question added by hand, likely as part of prebuilt question modules.
* Decide where context added for the agent is saved. It lasts only while the page is open.

**Fetching links on the server.** At onboarding auto generation, the server reads the page behind each link before it asks the model. It only does this from an approved list of URLs. However, code that fetches web pages on a server can be misused to reach places it should not, even with the list of allowed sites, the check on every redirect and the time limit in place. For now run Service Studio locally only. It will move to AWS Agent Core tool calls, which are more secure and reduce these vunerabilities, before it is hosted anywhere.

The link reading is in these files:

* `src/lib/server/shared/fetch-link.ts` is the only place the server fetches a web page, in `fetchLinkText`. It checks every redirect and stops after a time limit. This is the call to replace with an agent tool call.
* `src/lib/server/shared/allowed-link-domains.ts` holds the list of allowed sites and `isAllowedLink`, which checks a link against it.
* `src/lib/server/shared/read-links.ts` reads each link through `fetchLinkText` in `readLinks`, and gathers the text for the prompt.
* `src/lib/server/shared/generate-workflow.ts` calls `readLinks` before it asks the model. Both form and service onboarding go through it, so this is where an agent call would plug in.
* `src/lib/server/onboard-old/generate-service.ts`, in the old onboarding, also calls `fetchLinkText`. It is deleted along with the other `-old` folders.
