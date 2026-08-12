<script lang="ts">
  import { traceStore } from "$lib/stores/trace.svelte";
  import type { TraceEvent } from "$lib/common-trace";
  import { toJsonl } from "$lib/raw-trace";

  // The trace accumulates on the home page and is mirrored to sessionStorage,
  // so it is available here after navigation or a refresh.
  const trace = $derived(traceStore.trace);
  const rawTrace = $derived(traceStore.rawTrace);

  // Maps a run's terminal status to a GOV.UK tag colour.
  function statusTag(status: string): string {
    switch (status) {
      case "completed":
        return "govuk-tag--green";
      case "blocked":
        return "govuk-tag--orange";
      default:
        return "govuk-tag--grey";
    }
  }

  // Maps an event type to a GOV.UK tag colour, so the same kind of event is
  // easy to spot down the list.
  function eventTag(type: TraceEvent["type"]): string {
    switch (type) {
      case "interaction_available":
        return "govuk-tag--blue";
      case "values_proposed":
        return "govuk-tag--teal";
      case "values_submitted":
        return "govuk-tag--green";
      case "answer_presented":
        return "govuk-tag--purple";
      case "assistance_failed":
        return "govuk-tag--red";
      case "journey_finished":
        return "govuk-tag--orange";
      default:
        return "govuk-tag--grey";
    }
  }

  // A short, readable label for an event type.
  function eventLabel(type: TraceEvent["type"]): string {
    return type.replaceAll("_", " ");
  }

  // Renders a single scalar or object value compactly.
  function formatValue(value: unknown): string {
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }

  // Renders a values object as a compact, readable line. An ordinary scalar
  // answer stores its value under its own interaction id, so showing that
  // name again would just repeat what the interaction already is. It is only
  // shown when the object has more than one named part, such as an address
  // split into line, town, and postcode.
  function formatValues(values: Record<string, unknown>, interactionId: string): string {
    const entries = Object.entries(values);
    if (entries.length === 1 && entries[0][0] === interactionId) {
      return formatValue(entries[0][1]);
    }
    return entries.map(([key, value]) => `${key}: ${formatValue(value)}`).join(", ");
  }

  // The one line of detail worth showing for each kind of event.
  function eventDetail(event: TraceEvent): string {
    switch (event.type) {
      case "interaction_available":
        return "-";
      case "values_proposed":
      case "values_submitted":
        return formatValues(event.values, event.interaction_id);
      case "answer_presented":
        return "-";
      case "assistance_failed":
        return "The agent call did not produce a usable result this turn.";
      case "journey_finished":
        return `${Object.keys(event.result).length} value(s) in the final answer`;
      default:
        return "-";
    }
  }

  // Which order the table below is shown in. The exported common trace always
  // stays one flat, time-ordered list, since that order is itself meaningful
  // and other teams' tools expect it. This only changes how the same events
  // are laid out on the page: grouped keeps every event for one interaction
  // together, in the order they happened to it, rather than interleaved with
  // every other field's events. Chronological is the trace's own order.
  let eventView = $state<"grouped" | "chronological">("grouped");

  // The events to show, in the chosen order. Grouping never reverses the
  // order of one interaction's own events relative to each other, so working
  // out whether a value was revised (see isRevision below) gives the same
  // answer in both views.
  const orderedEvents = $derived.by(() => {
    if (!trace) return [];
    if (eventView === "chronological") return trace.events;

    const order: string[] = [];
    const byId = new Map<string, TraceEvent[]>();
    const runEvents: TraceEvent[] = [];
    for (const event of trace.events) {
      const id = "interaction_id" in event ? event.interaction_id : undefined;
      if (!id) {
        runEvents.push(event);
        continue;
      }
      if (!byId.has(id)) {
        order.push(id);
        byId.set(id, []);
      }
      byId.get(id)!.push(event);
    }
    return [...order.flatMap((id) => byId.get(id) ?? []), ...runEvents];
  });

  // True when an earlier event in the currently displayed order already
  // proposed a value for this same interaction, so this is a revision rather
  // than the only proposal ever made for that field.
  function isRevision(events: TraceEvent[], index: number): boolean {
    const event = events[index];
    if (event.type !== "values_proposed") return false;
    return events
      .slice(0, index)
      .some(
        (earlier) => earlier.type === "values_proposed" && earlier.interaction_id === event.interaction_id,
      );
  }

  // The Text/JSON format for the raw trace, offered purely as a copy/paste
  // artifact. The events table above already breaks the same run down
  // visually.
  let rawFormat = $state<"text" | "json">("text");
  let copied = $state(false);

  const rawTraceString = $derived.by(() => {
    if (!rawTrace) return "";
    if (rawFormat === "json") return toJsonl(rawTrace);
    return rawTrace.turns.map((turn) => `User: ${turn.user}\n\nAgent: ${turn.agentReply}`).join("\n\n");
  });

  // Legacy copy path for when the async Clipboard API is unavailable or blocked
  // (older browsers, missing permission, no document focus).
  function fallbackCopy(text: string) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  async function copyRawTrace() {
    const text = rawTraceString;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy(text);
      }
      copied = true;
    } catch {
      try {
        fallbackCopy(text);
        copied = true;
      } catch {
        copied = false;
      }
    }
    if (copied) setTimeout(() => (copied = false), 2000);
  }

  function downloadFile(filename: string, content: string, type: string) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  // Downloads the common trace, ready to be compared against other methods.
  function exportCommonTrace() {
    if (!trace) return;
    downloadFile(`common-trace-${trace.run.id}.json`, JSON.stringify(trace, null, 2), "application/json");
  }

  // Downloads the raw trace this common trace was derived from, matching the
  // filename the common trace's source_trace field already points to.
  function exportRawTrace() {
    if (!rawTrace || !trace) return;
    downloadFile(trace.source_trace ?? `raw-trace-${rawTrace.runId}.jsonl`, toJsonl(rawTrace), "application/jsonl");
  }
</script>

<div class="govuk-width-container page-fill">
  <main class="govuk-main-wrapper" id="main-content">
    <a class="govuk-back-link" href="/">Back to the form</a>

    <h1 class="govuk-heading-l">Run log</h1>
    <p class="govuk-body-m">
      A common trace of this agent run can be compared against other prototypes.
    </p>
    <p class="govuk-body-m">
      <a class="govuk-link" href="/compare">Compare against other methods &rarr;</a>
    </p>

    {#if !trace}
      <div class="govuk-inset-text">
        No run recorded yet. Upload a form on the <a class="govuk-link" href="/">home page</a> and
        send the agent a message, then come back here.
      </div>
    {:else}
      <dl class="govuk-summary-list">
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Run</dt>
          <dd class="govuk-summary-list__value"><code>{trace.run.id}</code></dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Implementation</dt>
          <dd class="govuk-summary-list__value"><code>{trace.run.implementation}</code></dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Journey</dt>
          <dd class="govuk-summary-list__value">
            {trace.initial_context?.form.name ?? trace.run.journey_id}
          </dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Status</dt>
          <dd class="govuk-summary-list__value">
            <strong class={`govuk-tag ${statusTag(trace.run.status)}`}>{trace.run.status}</strong>
          </dd>
        </div>
      </dl>

      <div class="govuk-button-group">
        <button type="button" class="govuk-button govuk-button--secondary" onclick={exportCommonTrace}>
          Export common trace (JSON)
        </button>
        <button type="button" class="govuk-button govuk-button--secondary" onclick={exportRawTrace}>
          Export raw trace (JSONL)
        </button>
      </div>

      <h2 class="govuk-heading-m">Events</h2>
      <p class="govuk-body-m">
        What happened within each interaction.
      </p>

      <div class="govuk-button-group" role="group" aria-label="Order to show events in">
        <button
          type="button"
          class={`govuk-button govuk-button--secondary ${eventView === "grouped" ? "is-active" : ""}`}
          aria-pressed={eventView === "grouped"}
          onclick={() => (eventView = "grouped")}
        >
          By interaction
        </button>
        <button
          type="button"
          class={`govuk-button govuk-button--secondary ${eventView === "chronological" ? "is-active" : ""}`}
          aria-pressed={eventView === "chronological"}
          onclick={() => (eventView = "chronological")}
        >
          Chronological
        </button>
      </div>
      {#if eventView === "chronological"}
        <p class="govuk-hint">
          The exact order events happened in, exactly as stored in the exported trace.
        </p>
      {/if}

      <table class="govuk-table">
        <thead class="govuk-table__head">
          <tr class="govuk-table__row">
            <th class="govuk-table__header">Event</th>
            <th class="govuk-table__header">Interaction Id</th>
            <th class="govuk-table__header">Detail</th>
          </tr>
        </thead>
        <tbody class="govuk-table__body">
          {#each orderedEvents as event, i (i)}
            {@const revised = isRevision(orderedEvents, i)}
            <tr class="govuk-table__row">
              <td class="govuk-table__cell">
                <strong class={`govuk-tag ${revised ? "govuk-tag--yellow" : eventTag(event.type)}`}>
                  {eventLabel(event.type)}{revised ? " revised" : ""}
                </strong>
              </td>
              <td class="govuk-table__cell">
                <code>{"interaction_id" in event ? (event.interaction_id ?? "-") : "-"}</code>
              </td>
              <td class="govuk-table__cell">{eventDetail(event)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h2 class="govuk-heading-m">Raw trace</h2>
      <p class="govuk-body-m">
        The full conversation this common trace was derived from.
      </p>
      <details class="govuk-details">
        <summary class="govuk-details__summary">
          <span class="govuk-details__summary-text">Show full transcript (copy &amp; paste)</span>
        </summary>
        <div class="govuk-details__text">
          <div class="govuk-button-group" role="group" aria-label="Transcript format">
            <button
              type="button"
              class={`govuk-button govuk-button--secondary ${rawFormat === "text" ? "is-active" : ""}`}
              aria-pressed={rawFormat === "text"}
              onclick={() => (rawFormat = "text")}
            >
              Text
            </button>
            <button
              type="button"
              class={`govuk-button govuk-button--secondary ${rawFormat === "json" ? "is-active" : ""}`}
              aria-pressed={rawFormat === "json"}
              onclick={() => (rawFormat = "json")}
            >
              JSON
            </button>
            <button type="button" class="govuk-button govuk-button--secondary" onclick={copyRawTrace}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre class="raw-pre">{rawTraceString}</pre>
        </div>
      </details>
    {/if}
  </main>
</div>

<style>

  .page-fill {
    font-family: "GDS Transport", arial, sans-serif;
  }

  :global(.govuk-button--secondary.is-active),
  :global(.govuk-button--secondary.is-active:hover),
  :global(.govuk-button--secondary.is-active:focus:not(:active):not(:hover)) {
    background-color: #1d70b8;
    color: #ffffff;
    box-shadow: 0 2px 0 #003078;
  }

  /* A code element has no bundled GDS monospace typeface to fall back to, so
     without this it renders in the browser's own default monospace font, at
     its own default size, which rarely matches the surrounding text. Sizing
     it relative to its context (em, not rem or px) keeps it matched wherever
     it appears, whether that is a summary list value or a table cell. */
  .page-fill :global(code) {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.95em;
  }

  /* A plain text preview box. There is no GDS "code block" component in this
     bundle, so this reuses the same monospace treatment as inline code. */
  .raw-pre {
    margin: 15px 0 0;
    padding: 0.75rem;
    background: #f3f2f1;
    border: 1px solid #b1b4b6;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.95em;
    line-height: 1.5;
  }
</style>
