<script lang="ts">
  import type { ActiveWorkflowSummary } from '$lib/types';

  let {
    workflows,
    onresume
  }: { workflows: ActiveWorkflowSummary[]; onresume: (workflowId: string) => void } = $props();
</script>

{#if workflows.length > 0}
  <details class="govuk-details" data-module="govuk-details">
    <summary class="govuk-details__summary">
      <span class="govuk-details__summary-text">Resume an active run ({workflows.length})</span>
    </summary>
    <div class="govuk-details__text govuk-!-padding-0">
      {#each workflows as workflow (workflow.id)}
        <div class="ss-card">
          <code>{workflow.id}</code>
          <span class="ss-muted">{workflow.status}</span>
          <button
            class="govuk-button govuk-button--secondary run-picker__resume govuk-!-margin-bottom-0"
            type="button"
            onclick={() => onresume(workflow.id)}
          >
            Resume
          </button>
        </div>
      {/each}
    </div>
  </details>
{/if}

<style>
  .run-picker__resume {
    margin-left: auto;
  }
</style>
