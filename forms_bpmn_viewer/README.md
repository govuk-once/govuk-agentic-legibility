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
  it is separate from the region expand/collapse controls. Inferred routing
  regions and repeat collections start collapsed. Report explains
  the inferred boundaries.
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
There is no editing or separate call-activity drill-down. Very large diagrams still require panning.

## Tests

```sh
npm test
```

The 28 Node tests cover catalogue discovery, multiple variants, missing/corrupt
sidecars, failed logs, refresh, containment, read-only HTTP endpoints, 505 form
folders, variant selection, question-reference matching, source feature classification
finite viewport calculations, including long and degenerate bounds, and routing
region classification, ancestor navigation and safe layout compression.
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
Groups have a bright blue, thicker border; collapsed groups also have a stronger
blue fill, distinguishing them from ordinary questions.
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

## Collapsible routing regions

Inferred routing regions and repeat collections start as compact, standard BPMN
collapsed subprocesses:
a rounded box with a boxed **+** marker, the opening question as its label and a
blue border. Click the **Expand region** button beside a box or in Selection to
show all its questions and routes in place. Repeat groups use **Expand collection**
/ **Collapse collection** controls. **Collapse region** reverses this.
The toolbar has **Expand all groups** / **Collapse all groups**; the overview
tracks the current view. Buttons beside boxes appear at 35% zoom or above;
Selection and toolbar controls remain available at lower zoom.

Navigating to an internal question or route automatically opens its enclosing
region. Collapse choices reset when loading a form or switching representations.
Subprocesses explicitly marked as inferred routing regions or repeat collections
start collapsed. Repeat collection labels retain their prefix so repetition is
visible in the compact view; expand a collection to see its complete loop.
Unrecognised subprocesses remain as generated.

This is a display-only transformation: original process IDs, conditions, metadata
and downloaded BPMN remain unchanged. No regeneration is needed. The converter
still writes expanded subprocesses for bpmn.io. The viewer rebuilds coordinates
from the original XML each time, shortening empty vertical bands beneath
collapsed process-level regions. If a parallel sibling occupies the same band,
that band is retained to avoid overlaps. Nested collapses hide their contents
but retain their enclosing subprocess's layout. This is deliberately conservative
rather than a general-purpose BPMN auto-layout engine.

Chromium checks also covered the supplied Veterans Badge diagram: collapsed
address region, repeated expand/collapse, expand/collapse all, automatic reveal
through question navigation, unchanged download, finite fit and preserved flow
structure. Its displayed vertical extent falls from 7,980 to 6,600 diagram units.

The supplied redundancies form was also checked in Chromium: both repeat
collections and its routing region start collapsed; expanding a collection
reveals its retained repeat control and loop. Individual/all toggles, overview
colours, finite fit, unchanged topology and byte-identical downloads passed.
Its displayed extent shortens from 17,730 to 9,808 diagram units.

## SFSM journeys and linked processes

The same viewer also reads `sfsm_bpmn` output. See
[`durable_poc/sfsm_bpmn/README.md`](../durable_poc/sfsm_bpmn/README.md) for conversion
commands. Keep the `.bpmn`, `.questions.json` and `.report.json` files together
inside a directory in the configured corpus. The catalogue adds SFSM journey,
Linked processes and API service calls filters, using the source definition.

Multi-process files show a Process selector. Select a call activity and click
**Open process**, or double-click its box; **Back to caller** restores the caller
selection. The breadcrumb includes nested calls. Questions and Previous/Next
show only the current process's source state listing. Full prompts, validation
schemas, API configurations, input/return mappings and outcome metadata remain
in the inspector. Report lists processes and disconnected source states.

The BPMN download includes all processes and planes. This navigation does not
change the original file or execute a journey. Existing Forms collapse controls,
font settings, overview, filters and viewport controls continue to work.

## Finding linked processes and seeing their parent

Call activities whose target process is included in the file have a purple fill
and border, retaining the standard thick BPMN border and boxed '+' marker. An
**Open process ↗** button appears below the box at 35% zoom or above; the inspector
and double-click navigation remain available at lower zoom.

The Overview uses the same purple for linked-process blocks and displays a
legend when links are present. Double-click a purple block to open its process.
Keyboard users can focus a block and press Enter or Space; arrow-key panning is
still available. Other task and grouped-subprocess colours remain unchanged.

A prominent banner identifies **Journey overview** versus **Inside a linked
process**, naming the current process and, when opened through a call, its parent
and originating call activity. The child canvas has a purple edge. Breadcrumbs
are clickable and return to the corresponding caller selection. A **Parent**
button gives a second explicit way back to the immediate caller.

If a process is selected directly, its banner lists all calling activities in
the file. These links open the parent diagram and select that call. This matters
for reusable processes: Calculate deadlines shows both timeline calls, rather
than implying that it has only one parent or that it was entered through a call
when it was actually selected directly.

These are viewer-only affordances; downloaded BPMN and process semantics are
unchanged. No regeneration is needed.

## Compact diagram layout

The title and toolbar are compact; the process scope badge now shares the
process-navigation row instead of occupying a separate banner. Breadcrumbs,
Back to caller, purple call activities and the child-canvas edge remain visible.
Longer explanations and the source identifier live in the **Details** popover.
**Parent calls** opens the calling activities, including multiple uses of shared
processes. Popovers float over the canvas without reducing its height; click
outside or press Escape to dismiss them. Conversion/import warnings stay visible.

The toolbar stays on one row and scrolls horizontally when space is limited;
its controls remain keyboard-accessible. The main app header and footer are also
smaller. On narrow/mobile layouts the process row can wrap to remain usable.

Chromium comparisons against patch 0011 measured canvas-height increases from
672 to 914 pixels at 1800×1100, and from 418.5 to 714 pixels at 1440×900. Checks
covered main and child processes, Details/Parent calls, Escape, shared-parent
navigation, linked-task styling and finite fit, alongside the Forms regressions.
These changes affect the viewer only; no BPMN regeneration is required.

## Label placement and linked-process background

External labels are rewrapped at the requested font size and then nudged within a
bounded neighbourhood. Candidate positions favour avoiding task/event/gateway
boxes, other labels and connecting lines. This is a deterministic, best-effort
viewer adjustment, not a full layout engine: dense junctions may still need zoom
or manual inspection. Task geometry, routing and downloaded BPMN remain unchanged.
The adjustment runs again on font changes without accumulating drift.

Entering a linked process tints the whole drawing surface light purple, matching
its call box. Returning to the main process restores the normal background.
Folded section introductions in newly generated SFSM BPMN appear in the call
activity's Selection panel; other source output tasks remain explicit.
