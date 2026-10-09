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
  Use journey-feature filters for repeatable questions, conditional routing,
  exits, optional questions, linear forms and inferred groups. Filter by source
  answer type (including types approximated by the compiler) or compiled answer
  kind such as `select_one`, `boolean` or `string`. Filters combine with search
  and issues; option counts describe the full catalogue, while the result count
  describes their intersection. Generated repeat-control questions are excluded
  from compiled-kind categories. Unknown metadata is not labelled linear.
  Navigate numbered pages of 30 forms rather than an ever-growing list.
- Switch between flat and **Grouped** diagrams. Grouped selects the converter's `auto` output;
  it is not an expand/collapse control. All questions stay visible within
  expanded subprocess outlines, and Report explains the inferred boundaries.
  **Auto (no groups)** means no safe boundary was found; the result remains flat. The selected source
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

The 18 Node tests cover catalogue discovery, multiple variants, missing/corrupt
sidecars, failed logs, refresh, containment, read-only HTTP endpoints, 505 form
folders, variant selection, question-reference matching, source feature classification
and finite viewport calculations, including long and degenerate bounds.
Fit uses BPMN coordinates for shapes, labels and connections, rather than cached
SVG bounds; Readable size and Focus selection reset the view directly. Chromium
checks covered fit from 100% and approximately 46%, complete-diagram visibility
and recovery from a zero-scale transform. Browser rendering
was also checked with Chromium against the four supplied Forms, including the
DVSA conditional branch and the IP repeatable question, both flat and auto views.
Neither the SFSM interpreter nor the BPMN interpreter is changed.

The small person drawn by bpmn-js is the standard BPMN User Task marker. It is
retained; hiding it or converting questions to untyped tasks would remove that
meaning. The viewer uses bpmn-js's standard renderer, with only selection/route
colour highlights. Existing BPMN files do not need regenerating for these changes.

## Overview and text size

The strip beside the canvas shows the whole journey and a blue viewport marker.
Click or drag to move without changing zoom. Focus the overview and use arrow
keys to pan; Home/End move to the top/bottom. This is a structural thumbnail,
without readable labels; the main canvas retains the standard BPMN symbols.
It does not cover the bpmn.io watermark, whose continued visibility is required
by the installed bpmn-js licence.

**Diagram text** selects a preferred diagram label size at 100% zoom (12–24px,
default 18px), retained locally in your browser. Long labels rewrap and shrink
individually to fit existing boxes. Gateway names, route conditions and event labels use the same selected size,
with label bounds enlarged and text rewrapped rather than squeezed into the old
small label box. No question wording is changed; full details remain in the
inspector. These controls affect this viewer only, not downloaded BPMN XML.
