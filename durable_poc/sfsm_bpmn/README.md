# SFSM → BPMN visualisation

Export an existing `sfsm/0.2` journey directly, without passing it through the
GOV.UK Forms parser. Reuses the Forms exporter's graph model, deterministic
layout, stable-ID encoding and BPMN diagram writer. Neither interpreter changes.

## Convert and browse Maternity Allowance

The attached schema matches the repository's existing `dwp_ma1_schema.json`.
From the repository root:

```sh
cd durable_poc
uv run python -m sfsm_bpmn \
  --input dwp_ma1_schema.json \
  --output ../bpmn_forms/maternity_allowance/journey.bpmn
cd ../forms_bpmn_viewer
npm start
```

Open http://127.0.0.1:5178 and refresh the catalogue. Search for Maternity
Allowance or select **SFSM journey** / **Linked processes** / **API service calls**
in the journey-feature filter. Existing Forms files can stay in the same corpus.
Restart an existing viewer server after applying the patch.

The converter writes:

- `journey.bpmn`: six processes, six diagram planes and local `calledElement`
  references in one portable file. The entry process is first.
- `journey.questions.json`: all 45 full prompts and input schemas, plus the
  unchanged original SFSM definition.
- `journey.report.json`: process inventory, warnings and unreachable states.

Keep these files together with their matching stems. In bpmn.io, the entry
process opens initially; the local viewer adds navigation between all planes.
**Download BPMN** returns the full original multi-process file.

Use the **Process** selector or select a call activity and click **Open process**.
Double-clicking a call activity also opens its target. **Back to caller** restores
selection of the originating call activity; the breadcrumb supports nested calls
such as Main → About your baby → Calculate deadlines. Questions and Previous/Next
are local to the displayed process and follow the source state listing, including
alternative branches; they do not simulate a respondent's path.

## Semantics

| SFSM state | BPMN |
| --- | --- |
| `input` | User task; full prompt, schema and assignment in local metadata |
| `choice` | Exclusive gateway; ordered rules become mutually exclusive guards |
| `call` | Service task; first API-error catch on `any` becomes an interrupting error boundary event |
| `assign` | Script task; original data operation retained as metadata |
| `output` | Task displaying the original source message |
| `invoke` | Call activity referencing a separately defined process |
| `end` | End event retaining status, outcome and returned data |

Each SFSM state has a stable BPMN ID qualified by process, a `sfsm:stateRef` with
its original process/state IDs, and its complete source state in `sfsm:state`.
Input tasks additionally reference the question sidecar. Process variables,
input/output mappings, HTTP configuration, captures and idempotency keys remain
metadata. Short task names come from state IDs or a short first prompt line;
no LLM summarisation or inferred business logic is used.

### Returned outcomes are different from API errors

The interpreter matches `invoke.catch` against a child's returned **outcome**,
regardless of status. A call activity therefore returns normally to an outcome
gateway. Its conditions use the explicitly documented `returned_outcome` and
`always` pseudo-operations within the visual condition JSON vocabulary. They
are not implicit SFSM variables. Earlier matching catches exclude later ones;
the default continues to `invoke.next`. Unhandled child outcomes also continue
to `invoke.next`, matching the existing interpreter.

`call.catch` catches an actual API activity exception. The current interpreter
only handles `on: any`; other service-call catch codes are rejected by the
exporter. If several `any` catches exist, only the first is reachable; the report
flags later handlers and the complete list remains in metadata. Error-boundary
flows are routed outside intervening tasks, not through their boxes.

## Scope and limitations

This is **non-executable BPMN** (`isExecutable="false"`). JSON predicates,
calculations, input mappings and service configuration are not standard engine
expressions or executable service implementations. Adapting these to an engine
is separate work. This converter does not call services, apply validation or
submit claims. In particular, the source's submission announcement is displayed
as an output task, not converted into an invented submission API call.

The explicit six-process decomposition is preserved; no additional arbitrary
hierarchy is inferred. Detailed process diagrams can still be long. Labels,
selection, zoom and linked navigation help inspection, but this remains the same
layered layout rather than a general-purpose optimising BPMN layout engine.

Unsupported schema versions, state types/fields, missing transition targets,
invalid invoked processes, recursive process calls and unsupported service-error
catch codes fail explicitly before outputs are written. Validation/answer-schema
content is preserved as supplied, not interpreted. Unreachable source states are
retained as disconnected shapes and listed in Report; `main/end_exception` is
one such state in Maternity Allowance. Normal loops and correction/retry flows
within a process are supported.

The Forms-specific `forms_bpmn.relayout` command continues to apply only to its
single-process Forms outputs; it does not relayout these multi-process files.

## Tests and independent validation

From `durable_poc`:

```sh
uv run python -m pytest sfsm_bpmn/tests forms_bpmn/tests -q
cd ../forms_bpmn_viewer
npm test
```

The conversion tests account for all 152 source states, every transition and
catch, six linked process references, shared deadline calculations, first-match
conditions, error-boundary attachments, question metadata, stable IDs,
determinism, unreachable states, malformed DI and unsupported features. Existing
Forms conversion and viewer tests remain included.

The generated Maternity Allowance XML was independently validated against the
BPMN 2.0 XSDs distributed with `bpmn-moddle` and rendered with bpmn-js in Chromium,
with no import warnings. Browser checks covered all six planes, call navigation,
return to caller, process-local question lists, API metadata, reports, finite fit
and byte-identical downloads, alongside the existing Forms browser regressions.
