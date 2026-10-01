<script lang="ts">
  interface TraceLine {
    category: string;
    summary: string;
    detail?: unknown;
    timestamp?: string;
  }

  let { traces }: { traces: TraceLine[] } = $props();
</script>

<details class="govuk-details" data-module="govuk-details">
  <summary class="govuk-details__summary">
    <span class="govuk-details__summary-text">Trace ({traces.length})</span>
  </summary>
  <div class="govuk-details__text govuk-!-padding-0">
    {#each traces as trace, index (index)}
      <div class="ss-card trace-sidebar__row">
        <span class="govuk-tag govuk-!-margin-right-2">{trace.category}</span>
        <span class="govuk-body-s govuk-!-margin-0">{trace.summary}</span>
        {#if trace.timestamp}
          <span class="ss-muted govuk-body-s govuk-!-margin-0 trace-sidebar__timestamp">{trace.timestamp}</span>
        {/if}
      </div>
    {:else}
      <p class="govuk-body-s ss-muted">No trace events yet.</p>
    {/each}
  </div>
</details>

<style>
  .trace-sidebar__row {
    gap: 10px;
  }

  .trace-sidebar__timestamp {
    margin-left: auto;
  }
</style>
