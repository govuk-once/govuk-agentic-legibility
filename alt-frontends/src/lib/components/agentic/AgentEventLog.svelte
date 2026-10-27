<script lang="ts">
  // Shared (src/lib/agentic/event-tags.ts): how each kind of event is labelled and coloured
  import { awaitingToken, categoryText, tagColour, type RunEventLine } from '$lib/agentic/event-tags';

  interface Props {
    events: RunEventLine[];
    /** Whether the raw detail of each event is shown in a column of its own. */
    showTechnical: boolean;
  }

  let { events, showTechnical }: Props = $props();

  interface LogRow {
    number: number;
    event: RunEventLine;
    /** True for the event where the agent stopped to ask you something. */
    pausedHere: boolean;
  }

  interface Part {
    title: string;
    rows: LogRow[];
    /** A line after the part, when the agent stopped at its end. */
    pausedNote?: string;
  }

  // The log is split into parts at each point where the agent stopped to ask you something. The first
  // part is the agent working on its own, and each later part is what happened after you answered.
  const parts = $derived.by((): Part[] => {
    const result: Part[] = [];
    let current: Part = { title: 'Part 1 · the agent working alone', rows: [] };
    events.forEach((event, index) => {
      const pausedHere = event.summary?.startsWith('Escalated to human') ?? false;
      current.rows.push({ number: index + 1, event, pausedHere });
      if (pausedHere) {
        current.pausedNote = `paused at event ${index + 1} · waiting for your answer`;
        result.push(current);
        current = { title: `Part ${result.length + 1} · after you answer`, rows: [] };
      }
    });
    if (current.rows.length > 0) result.push(current);
    return result;
  });

  // The raw detail of an event as one short line of text.
  function technicalText(detail: unknown): string {
    if (detail === undefined || detail === null) return '';
    const text = typeof detail === 'string' ? detail : JSON.stringify(detail);
    return text.length > 90 ? `${text.slice(0, 89)}…` : text;
  }
</script>

<div class="agent-log" class:agent-log--technical={showTechnical}>
  <div class="agent-log__heading govuk-!-font-size-16">
    <span class="agent-log__number">#</span>
    <span class="agent-log__text">what happened</span>
    {#if showTechnical}
      <span class="agent-log__technical">technical</span>
    {/if}
    <span class="agent-log__by">by</span>
  </div>

  {#each parts as part (part.title)}
    <h3 class="govuk-heading-s govuk-!-font-size-16 govuk-!-margin-0 agent-log__part">{part.title}</h3>

    {#each part.rows as row (row.number)}
      {@const token = awaitingToken(row.event.summary)}
      <div class="agent-log__row" class:agent-log__row--paused={row.pausedHere}>
        <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 ss-muted agent-log__number">#{row.number}</span>
        <span class="govuk-body govuk-!-margin-0 agent-log__text">
          {#if token}
            <strong>Awaiting input</strong> [{token}]
          {:else}
            {row.event.summary}
          {/if}
        </span>
        {#if showTechnical}
          <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 ss-muted agent-log__technical">
            {technicalText(row.event.detail)}
          </span>
        {/if}
        <span class="agent-log__by">
          <span class="govuk-tag {tagColour(row.event)}">{categoryText(row.event.category)}</span>
        </span>
      </div>
    {/each}

    {#if part.pausedNote}
      <p class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 agent-log__paused">{part.pausedNote}</p>
    {/if}
  {:else}
    <p class="govuk-body ss-muted agent-log__empty">No events yet.</p>
  {/each}
</div>

<style>
  /* The headings and the small notes are set in a fixed-width typeface, as in the design. */
  .agent-log__heading,
  .agent-log__paused,
  .agent-log__number {
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
  }

  .agent-log__heading,
  .agent-log__row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding-inline: 20px;
  }

  .agent-log__heading {
    padding-block: 12px;
    border-top: 1px solid #b1b4b6;
    border-bottom: 1px solid #ecece8;
    color: #505a5f;
  }

  .agent-log__number {
    flex: 0 0 48px;
  }

  .agent-log__text {
    flex: 1 1 0;
    min-width: 0;
  }

  .agent-log__technical {
    flex: 0 0 300px;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .agent-log__by {
    flex: 0 0 110px;
  }

  /* A grey band marks the start of each part. */
  .agent-log__part {
    padding: 12px 20px;
    background-color: #f3f2f1;
  }

  .agent-log__row {
    padding-block: 12px;
    border-bottom: 1px solid #ecece8;
  }

  /* The event where the agent stopped to ask you something has a yellow outline. */
  .agent-log__row--paused {
    box-shadow: inset 0 0 0 2px #ffdd00;
  }

  /* A dashed red line and note after a part that ended with the agent stopping. */
  .agent-log__paused {
    margin: 0;
    padding: 12px 20px;
    border-bottom: 1px dashed #d4351c;
    color: #d4351c;
    text-align: right;
  }

  .agent-log__empty {
    padding: 20px;
    margin: 0;
  }
</style>
