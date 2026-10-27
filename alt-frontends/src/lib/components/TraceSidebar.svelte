<script lang="ts">
  interface TraceLine {
    category: string;
    summary: string;
    detail?: unknown;
    timestamp?: string;
  }

  let { traces }: { traces: TraceLine[] } = $props();

  // "ENGINE" becomes "Engine".
  function categoryText(category: string): string {
    return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
  }

  // The engine reports a question waiting for an answer as "Awaiting InputState [tkn_15]". That row
  // is picked out with a yellow tag, and its token is shown apart from the words.
  function awaitingToken(summary: string): string | null {
    return /^Awaiting InputState \[(.+)\]$/.exec(summary)?.[1] ?? null;
  }

  function tagColour(trace: TraceLine): string {
    if (awaitingToken(trace.summary)) return 'govuk-tag--yellow';
    return trace.category.toLowerCase() === 'user' ? 'govuk-tag--blue' : 'govuk-tag--grey';
  }
</script>

<section aria-labelledby="trace-heading">
  <div class="trace-sidebar__heading">
    <h2 id="trace-heading" class="govuk-heading-s govuk-!-margin-0">Trace</h2>
    <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 ss-muted">
      {traces.length}
      {traces.length === 1 ? 'event' : 'events'}
    </span>
  </div>

  {#each traces as trace, index (index)}
    {@const token = awaitingToken(trace.summary)}
    <div class="ss-card trace-sidebar__row">
      <span class="trace-sidebar__tag"><span class="govuk-tag {tagColour(trace)}">{categoryText(trace.category)}</span></span>
      <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0">
        {#if token}
          <strong>Awaiting input</strong> [{token}]
        {:else}
          {trace.summary}
        {/if}
      </span>
      {#if trace.timestamp}
        <span class="ss-muted govuk-body-s govuk-!-margin-0 trace-sidebar__timestamp">{trace.timestamp}</span>
      {/if}
    </div>
  {:else}
    <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-top-2">No trace events yet.</p>
  {/each}
</section>

<style>
  .trace-sidebar__heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding-bottom: 8px;
    border-bottom: 2px solid #1d70b8;
  }

  /* Rows sit flush with the heading's edges instead of being padded in like a card. */
  .trace-sidebar__row {
    align-items: flex-start;
    gap: 12px;
    padding: 10px 0;
  }

  /* A fixed column so the words line up whichever tag is beside them. */
  .trace-sidebar__tag {
    flex: 0 0 96px;
  }

  .trace-sidebar__timestamp {
    margin-left: auto;
  }
</style>
