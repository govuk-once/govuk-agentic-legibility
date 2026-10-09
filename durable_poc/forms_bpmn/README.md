# GOV.UK Forms → BPMN visualisation spike

This exports a **non-executable** BPMN process with a visible user task for every
source question, explicit exclusive routing and diagram coordinates for bpmn.io.
It reuses the Forms compiler rather than defining a second Forms routing parser.

## Architecture and branch integration

The supplied bundle has `main` at `927e182` and `bpmn-coa` at `615a64e`.
`main` contains `forms_adapter/compiler.py`: `normalise_form` unifies `question`
and `question_page`; `compile_form` validates inputs/routes and emits SFSM input,
choice, append, output and terminal states. Presentation metadata keeps the original
question text, headings, guidance, options and answer settings. Dates, addresses,
numbers and several other inputs become primitive strings; these are not complete
Forms validation implementations. Repeatable questions add append and “another
answer?” states; exits have their own output and terminal states. Conditional
rules are tested in order and the first matching rule wins.

This branch carries **only** `forms_adapter/__init__.py` and `compiler.py`, unchanged
from that `main` commit. The full adapter's preview was deliberately not brought
over: it depends on `main`'s `append_path` helper, which `bpmn-coa` lacks. Bringing
it over would require runtime changes unrelated to this visualisation spike.
No SFSM or BPMN interpreter files are changed. Once the branches are merged,
these identical compiler files can be shared normally.

Pipeline:

1. Existing normalisation and SFSM compilation.
2. SFSM graph projection to BPMN tasks, exclusive gateways, collection append
   script tasks, exit-display tasks and end events.
3. Optional conservative decomposition, followed by explicit merge gateways.
4. Deterministic layered layout, BPMN DI, structural validation and SVG preview.

Mary's BPMN spike uses a different execution contract: `meta:form` holds fields
and UI wording inside user tasks; `meta:taskHandler` selects handlers;
`meta:processContract` describes process inputs/outputs; call activities invoke
named child processes with explicit variable mappings; boundary error events
handle failures. Gateway expressions are strings such as `confirmed == true`.
The inspected Temporal parser supports call activities but does not parse embedded
`subProcess` elements. The existing BPMN files lack DI layout.

This exporter adopts standard BPMN task/gateway notation but uses a separate
`forms` metadata namespace and JSON predicate expressions. It **does not claim
compatibility with Mary's interpreter**. The XML has `isExecutable="false"`.
Making it executable on any engine would require deliberate question-handler,
variable, predicate and collection contracts. Standard XML and diagram validity
are separate from portable execution semantics.

## Representations

`--mode flat` exposes every question and generated control step in one process.
`--mode auto` adds expanded embedded subprocesses, keeping the detail visible:

- Explicit repeatable collection is grouped when its compiled control nodes have
  one entry and one continuation. Its loop remains explicit inside the box.
- A branching region begins at a question followed by a split and ends immediately
  before its nearest common postdominator. Every path must reach that continuation.
  It must be acyclic, have only one entry/continuation, contain at least three source
  questions and contain no escaping terminal or already-grouped subprocess.
- Outer regions win when candidates overlap; nested routing remains visible.
- Page headings do not create groups. Arbitrary linear runs do not create groups.
- These are **structural** regions, not proof of reusable business capabilities.
  Generated titles quote the entry question; no business-purpose labels are guessed.

Call activities are not generated. A genuinely reusable subprocess needs an
explicit definition, input/output contract and ownership; the Forms exports do
not provide those. Expanded embedded subprocesses are an honest representation
of local grouping and can be collapsed manually in a modeller if useful.

### Supplied examples

| Form | Questions | Behaviour | Auto grouping |
| --- | ---: | --- | --- |
| 6, holiday pay amendment | 11 | Linear; four optional amendment questions | None |
| 5871, LPG statistics | 17 | Linear; optional feedback | None |
| 7530, DVSA logo | 9 | ADI vs motorcycle; motorcycle sub-branch | Q3–Q8 routing region |
| 265080, IP account | 8 | Visible patent vs alternative identifier; repeated missing numbers | Q3–Q5 routing region and Q6 repeat collection |

There are real conditional examples in the supplied files, so a synthetic form
is not needed to demonstrate branching. Tests also include an explicitly labelled
synthetic example for overlapping checkbox rules and early exits; that example
is useful for edge-case validation the real examples do not cover.

## Question metadata and conditions

Each user task has a stable XML-safe ID derived injectively from its source state
ID and a `forms:questionRef` pointing into a neighbouring `.questions.json` file.
The sidecar contains the compiled input schema, original presentation settings,
assignment path, generated-control flag and **complete unmodified source export**.
`sourceStepId` identifies the original question even for a repeat-control task.
Renaming/moving BPMN requires keeping the sidecar reference valid. bpmn.io displays
the graph but does not implement a question inspector for this custom extension.
It can open the BPMN alone; rich metadata use requires retaining the sidecar.

Conditional flows have readable labels and formal expressions using
`urn:govuk:sfsm:predicate-json:v1`. For later rules the exporter emits:
`rule AND NOT(any earlier rule)`. This is essential: checkbox routes can overlap,
whereas BPMN does not define a portable “first matching outgoing flow” policy.
Default flows stay unconditional and are marked on their gateway. The predicate
JSON uses the existing SFSM `all`, `any` and `condition` combinator vocabulary.
Unconditional source jumps become ordinary sequence flows. A skip-to-end means
answers collected; an exit page means an offramp, not successful submission.

## Run

Use the repository's Python 3.14 environment. From the repository root:

```bash
uv sync --group dev
cd durable_poc
uv run python -m forms_bpmn \
  --input forms_bpmn/tests/fixtures/7530.json \
  --output /tmp/forms-bpmn/7530.flat.bpmn \
  --mode flat
uv run python -m forms_bpmn \
  --input forms_bpmn/tests/fixtures/7530.json \
  --output /tmp/forms-bpmn/7530.auto.bpmn \
  --mode auto
uv run pytest forms_bpmn/tests -q
```

Each conversion writes `.bpmn`, `.questions.json`, `.report.json` and `.svg`.
Open the BPMN in https://demo.bpmn.io/ or view the SVG in a browser. The converter
has no added runtime dependencies beyond the existing compiler's Pydantic model;
its layout, validation and SVG renderer use the Python standard library.

To regenerate both views for the fixtures, from `durable_poc`:

```bash
for input in forms_bpmn/tests/fixtures/*.json; do
  name=$(basename "$input" .json)
  for mode in flat auto; do
    uv run python -m forms_bpmn --input "$input" \
      --output "/tmp/forms-bpmn/$name.$mode.bpmn" --mode "$mode"
  done
done
```

The converter validates before writing. A failure has a non-zero exit status;
previous outputs, if present, remain old and must not be mistaken for a new result.

## Independent validation

The mandatory Python validator checks ID uniqueness, scope-local references,
reachability, incoming/outgoing consistency, gateway defaults, linked questions,
DI coverage, finite coordinates, endpoint docking and subprocess containment.
The tests also check that routed lines do not pass through unrelated shapes in
all eight supplied-form representations.

Optional independent checks use bpmn.io's model library and official BPMN XSDs
bundled with it. From `durable_poc`:

```bash
npm ci --prefix forms_bpmn/qa
uv run --with lxml python forms_bpmn/qa/check-xsd.py /tmp/forms-bpmn/*.bpmn
node forms_bpmn/qa/check-import.mjs /tmp/forms-bpmn/*.bpmn
```

The QA package/lockfile pins `bpmn-moddle` 10.3.1. This is not a runtime dependency.
All eight generated example files passed both checks. The DVSA expanded view
was additionally imported into the live bpmn.io modeller and displayed correctly.
The supplied SVGs are produced by our convenience renderer using the same DI
coordinates; they are not exports from bpmn.io.

## Unsupported features and scope

- Payment URLs are rejected: the existing compiler invents a simulated payment
  interaction, which is inappropriate for a faithful process visualisation.
- Unknown answer types are rejected rather than accepted through the compiler's
  preview-only string fallback. Known scalar types retain their source settings.
- The compiler's existing explicit rejections remain: ambiguous destinations,
  invalid selection definitions, unknown targets, future checked-page references,
  conflicting/unused exits, unsupported multi-file settings and routing based on
  repeatable answers, among others. It supports ordinary repeatable collection;
  repeatability is not categorically unsupported on this version of `main`.
- Unreachable source questions are rejected. An unused generated normal-completion
  event is omitted when all real paths exit early.
- Check-answers pages, declaration acceptance, department submission, payment,
  confirmation, back/edit navigation and backend validation are not inferred.
  Source metadata for these remains available, but the end says “Answers collected”.
- A source backward jump can remain in the flat graph. Cyclic routing regions
  are not inferred as subprocesses; deeply complex routing/layout is not evaluated
  by these four examples. Layering uses exterior lanes for loops/long skips.
- Full question labels and long conditional values can make diagrams tall/wide.
  Pan/zoom is necessary; the layout is a deterministic PoC, not a general-purpose
  industrial layout engine. Labels/crossings need further review on a larger corpus.

## Assessment

BPMN is useful on these examples mainly because it exposes questions that are
mutually exclusive, branches that skip questions and repeated data collection.
The DVSA flat diagram already reveals most of that value. Its expanded region
adds a boundary separating shared identity/contact collection from trainer-dependent
questions, but also adds start/end/container notation and height. The IP repeat
collection has the strongest source-grounded decomposition rationale.

The linear forms gain little: a linked task list is not substantially better than
a clear question inventory. Their headings might suggest human-authored groups,
but they do not establish independent subprocesses, so neither is grouped here.
Separating process references from question metadata works, but could also be
done with SFSM; it is not uniquely an advantage of BPMN.

These results justify BPMN as a review/visualisation projection and a possible
shared modelling vocabulary. They do **not** establish a case for replacing the
execution engine, nor that hundreds of forms can be decomposed into meaningful
reusable services automatically. The next useful evaluation is whether designers,
service owners and engineers can identify routing errors or missing questions
more quickly using these diagrams than a structured question/route table.

Layout uses the actual widths in each row, rather than applying the widest
subprocess width to every column. Bypass/return lanes clear only the rows crossed
by that route, and disjoint routes can reuse lanes. These remain orthogonal
connections around intervening questions; they do not represent extra questions.
Existing exports must be regenerated to obtain the more compact BPMN DI.
