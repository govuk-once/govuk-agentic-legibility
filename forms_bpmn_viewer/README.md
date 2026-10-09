# Local Forms BPMN explorer

Browse the converter's output without uploading individual diagrams. Uses the
bpmn.io `bpmn-js` navigated viewer; this is a read-only inspection tool.
It does not execute journeys or change generated files.

## Run

Requires Node.js 20 or newer. From the repository root:

```sh
cd forms_bpmn_viewer
npm ci
npm start
```

Open http://127.0.0.1:5178. By default the server reads `bpmn_forms` in the
repository root, regardless of your current working directory. For another folder:

```sh
npm start -- --dir /absolute/path/to/bpmn_forms --port 5180
```

The server listens on localhost. Dependencies are installed once; assets and form
data are served locally, with no CDN or external question-reference requests.
Stop with Ctrl+C. Click **Refresh catalogue** after generating more forms.

## Expected files

One directory per form, with one or more representations:

```text
bpmn_forms/
  7530/
    form.bpmn
    form.questions.json
    form.report.json
    conversion.log
```

The JSON sidecars must have the same filename stem as their BPMN file. For
comparison, generate `7530.flat.bpmn` and `7530.auto.bpmn` with their respective
sidecars in the same folder. The converter writes question references using the
sidecar filename: move the files together, retaining their names. Arbitrary BPMN
filenames work, including the existing `form.bpmn` batch output. Root-level BPMN
files are supported as a single catalogue entry. Only the root and its immediate
subdirectories are scanned.

Missing or malformed sidecars appear as issues; the BPMN can still be viewed.
Folders containing only `conversion.log` also appear, so failed conversions are
visible. Logs containing `UNSUPPORTED:` or a Python traceback mark existing
outputs as potentially stale. This is a diagnostic heuristic, not proof that
conversion succeeded. Only converter-produced sidecar schemas are supported.

## Explore

- Search form names, IDs and folders; filter entries with conversion issues.
  The catalogue progressively displays 100 entries at a time.
- Switch between flat and automatically grouped diagrams. The selected source
  question is retained where possible. Automatic grouping is selected initially.
- Pan, zoom, fit the journey or focus the selected question. Click shapes or
  connections; connected routes are highlighted. The initial view focuses on
  the first question at readable scale, rather than shrinking a long form.
- **Selection** shows question wording, answer type, validation/settings,
  original routing, help text, exit information and compiled metadata. Decisions
  show their outgoing conditions and default route; click a route to inspect it.
- **Questions** and Previous/Next navigate source export order. Alternative
  branches remain in that list: it is not an executed respondent path.
- **Report** shows converter warnings and grouping reasons, links each group
  to its diagram, and includes the conversion log when present.
- **Source** exposes original export, question definitions and BPMN XML.
  Download the selected BPMN or its JSON sidecars.

Question references are resolved only against the matching local sidecar.
Help text is displayed as plain text/Markdown, without executing embedded HTML.
Repeatable questions and exit pages are shown through retained metadata; this
viewer does not simulate validation, route selection or repeatable collections.
Subprocesses are expanded as emitted by the converter; there is no editing or
separate call-activity drill-down. Very large diagrams still require panning.

## Tests

```sh
npm test
```

The Node tests cover catalogue discovery, multiple variants, missing/corrupt
sidecars, failed logs, refresh, containment, read-only HTTP endpoints, 505 form
folders, variant selection and question-reference matching. Browser rendering
was also checked with Chromium against the four supplied Forms, including the
DVSA conditional branch and the IP repeatable question, both flat and auto views.
Neither the SFSM interpreter nor the BPMN interpreter is changed.
