# GOV.UK Forms → SFSM adapter (local web preview)

This small, deliberately conservative adapter compiles exported Forms **into the repository's
existing `sfsm/0.2` model**. It does not modify the Temporal interpreter, send a form,
take payment, upload files or involve an LLM. Use **synthetic answers only** in the local
preview: values remain in process memory, and there is no authentication or persistence.

## Compile

Run from the repository root, with its Python dependencies installed:

```sh
cd durable_poc
python -m forms_adapter --input ../forms_export/6.json --output ../compiled_forms/6.json
python -m forms_adapter --input ../forms_export/2130.json --output ../compiled_forms/2130.json
python -m forms_adapter --batch ../forms_export --output ../compiled_forms --report ../compiled_forms/report.json
```

If you do not yet have the exports, use the two **committed example-export fixtures**:

```sh
python -m forms_adapter --input forms_adapter/tests/fixtures/6.json --output ../compiled_forms/6.json
python -m forms_adapter --input forms_adapter/tests/fixtures/2130.json --output ../compiled_forms/2130.json
```

Both `forms_export` and the generated `compiled_forms` are gitignored. Batch compilation
prints individual failures and writes a JSON status/reason report without stopping the
remaining exports; single-form compilation exits nonzero when unsupported.

## Web journey

Start the local SFSM preview API from `durable_poc`:

```sh
python -m uvicorn forms_adapter.preview:app --host 127.0.0.1 --port 8002
```

In another terminal, from the repository root:

```sh
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173/forms?id=2130> or `?id=6`. The new route reuses the
existing Svelte `SchemaForm` component; the local server validates the compiled SFSM
model, presents only its *current* input state, and traverses the compiled native
`choice` states with `src.predicates.evaluate`. No agent chooses the next page. This is
an isolated preview API; the existing DVLA/Flex API on port 8001 is unchanged.

## Scope and explicit limitations

* Both `question_page` and `question` normalise to identical steps. Source IDs,
  headings, question text, hints, guidance and answer settings are retained in the
  input's `schema.presentation` metadata. The web preview displays guidance as
  preformatted Markdown source, not rendered HTML.
* Selection becomes native `select_one`/`select_many`. Source labels and values are
  preserved. Optional `select_one` gains an explicit `Skip this question` option
  (`__forms_skip__`) because the existing interpreter otherwise rejects skipped
  selections. An empty optional text is stored as an empty string. No new validation
  or special handling is added to the interpreter.
* Every name configuration compiles to **one string input**, retaining the original
  `answer_settings` (full name, separate components, title, etc.) in presentation
  metadata. The current generic preview shows one text box; a Forms-aware frontend
  can use that metadata to display separate name fields later. UK-only addresses
  (line 1, optional line 2, town, postcode) still become consecutive native `input`
  states with deterministic suffixes. Date, number, email and NINO are also
  conservatively **string inputs**, not format-validated. The web renderer uses
  date/email input affordances.
* Native `choice` predicates implement selection `answer_value` → `goto_page_id`
  and `skip_to_end`, with `next_step_id` the default route. Multiple-choice routing
  uses the interpreter's native `contains` predicate. Conditions are tested in export
  order, so first matching rule wins. Cross-page checks and non-selection routing
  are deliberately rejected, not approximated.
* Repeatable questions, file uploads, payment integration, exit-page flows, unknown
  answer/step types, ambiguous or broken references, and non-selection routing are
  reported as unsupported. Declarations and `what_happens_next` are metadata only;
  a terminal state means **answers collected locally**, not submitted.
* The preview runner is deliberately not a Temporal implementation: it supports the
  adapter's input/choice/end subset using the **real SFSM model and predicates**.
  Running the full Temporal workflow requires the project's Temporal environment.

Run focused tests from `durable_poc` with `python -m pytest forms_adapter/tests -q`.
