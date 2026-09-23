# GOV.UK Forms → SFSM adapter (local web preview)

This adapter compiles exported Forms **into the repository's existing `sfsm/0.2`
model**, keeping question collection separate from frontend presentation. It does not
change the Temporal interpreter beyond a generic list-append operation, submit a form, take payment, upload file *bytes* or
involve an LLM. Use **synthetic answers only** in the local preview: values remain
in process memory, and there is no authentication or persistence.

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
remaining exports; single-form compilation exits nonzero when unsupported. Successful
entries may also include `warnings` about deliberate simplifications (for example,
addresses collected as a string, file references needing an uploader, or unfamiliar
answer types falling back to a string). Warnings do not alter the SFSM schema.
Batch reports distinguish `ok`, `preview_only` (payments omitted or unknown
answer types) and `unsupported`. Only `ok` contributes to the "Compiled" count.
If an export was previously converted but now fails stricter validation, its
stale generated JSON is deleted, preventing the filesystem server from serving it.

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
* **One input state per non-repeatable Forms question**, keeping the original step ID. Ordinary
  answers (including names, UK/international addresses, telephone numbers, dates,
  NINOs and previously unseen scalar types) become unrestricted `string` inputs.
  `schema.presentation` retains all original Forms `answer_type`, `answer_settings`,
  question text, headings, hint and guidance, so different channels can present
  richer controls without changing the process graph. An unknown answer type is
  also flagged in the batch report for review; it is not rejected by an allow-list.
* Selections with known cardinality and valid options use `select_one` or
  `select_many`. **Required, routed** Yes/No selections become native `boolean`
  inputs, so an agent submits `true`/`false` and routing uses `is_true`/`is_false`.
  A plain, unrouted Yes/No *text* question remains a string. An optional
  `select_one` includes an explicit `__forms_skip__` option because the current
  interpreter otherwise rejects skipped selections. An ambiguous **unrouted**
  selection (routed or not) is rejected rather than flattened into a string.
* Deterministic `choice` states handle `answer_value` → `goto_page_id` and
  `skip_to_end`, defaulting to `next_step_id`. A string is compared with `eq`,
  multiple selections with `contains`, and boolean Yes/No with the native boolean
  predicates. A condition may check an earlier question; conditions referencing a
  later question or invalid destination is rejected. Referenced exit pages compile
  to an `output` state carrying their heading and guidance, followed by an
  off-ramp `end` state. Malformed and unresolved exit pages reject compilation.
  Clients never
  choose the next node independently.
* A Forms `file` question becomes an existing SFSM `file_ref` input,
  preserving its source answer settings. The Temporal interpreter accepts a value
  such as `{"ref": "synthetic-1", "bytes": 128, "content_type": "application/pdf"}`.
  **This does not itself upload any bytes or implement storage**, and no upload API
  call is generated. An upload-capable client must provide a reference; the current
  Svelte preview does not provide a file-upload control (its JSON API can accept
  pre-uploaded refs). Optional `file_ref` questions can now be skipped by sending
  `null`, or answered with a valid uploaded reference. The new `forms_frontend`
  has an opt-in local synthetic-file uploader; the compiler itself stores no
  bytes. Multiple-file inputs are still unsupported.
* Omitted/null `is_optional` and `is_repeatable` are interpreted as `false`.
  Required repeatable questions without routing compile to ordinary SFSM input,
  assign and choice states. The original input is revisited for each answer;
  a generic `append` assignment stores all answers, in order, at
  `answers.<step_id>`, and a synthetic boolean "Do you want to add another
  answer?" input controls the loop. Temporal still issues a fresh token for
  every revisit. Selections retain their type, including list-valued
  `select_many` answers. Addresses retain the adapter's *existing* one-string
  representation and source presentation settings, rather than gaining new
  structured address fields in this increment. Optional repeatables and any
  routing from or referring to repeatable answers remain unsupported and fail
  compilation. The export does not specify repetition limits, so the generated
  loop has no maximum. Automatic proposals hand repeat-loop control to a user
  rather than guessing when all answers have been supplied. Payments are flagged
  `preview_only`; malformed routing remains unsupported. Declarations
  and `what_happens_next` are metadata only; `end_form` means **answers collected**,
  not submitted or paid for.
* The preview runner is deliberately not a Temporal implementation: it supports the
  adapter's input/assign/choice/output/end subset using the **real SFSM model and predicates**.
  Running the full Temporal workflow requires the project's Temporal environment.

Run focused tests from `durable_poc` with `python -m pytest forms_adapter/tests -q`.

For Form 691, both `NhGF9hjQ` (establishment address, via the existing address
string input) and `S1vHVvFS` (per-site redundancy count, text) become loops.
Batch compilation continues to reject unsupported repeatable combinations.

To run the focused suite locally (not required to apply the patch):

```sh
cd durable_poc
python -m pytest forms_adapter/tests tests/test_pure.py -q
cd ..
python -m pytest forms_frontend/tests/test_proposals.py -q
```

A full Temporal integration run additionally requires the project's Temporal
Python dependencies and the Temporal CLI binary, then `cd durable_poc &&
python -m pytest forms_adapter/tests/test_repeatable_temporal.py -q`. The local preview tests are **not**
a substitute for a running Temporal worker.
