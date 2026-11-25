<script lang="ts">
  import { goto } from '$app/navigation';
  import { DurableApiError, listWorkflows, startRun } from '$lib/api/client';
  import type { WorkflowSummary } from '$lib/types';

  let workflows: WorkflowSummary[] = $state([]);
  let loadError: string | null = $state(null);
  let startError: string | null = $state(null);
  let startingId: string | null = $state(null);

  $effect(() => {
    listWorkflows()
      .then((result) => (workflows = result))
      .catch((error: unknown) => {
        loadError = error instanceof DurableApiError ? error.message : 'Failed to load workflows';
      });
  });

  async function start(workflowId: string) {
    startError = null;
    startingId = workflowId;
    try {
      const { workflow_id } = await startRun(workflowId);
      await goto(`/web/${encodeURIComponent(workflow_id)}`);
    } catch (error) {
      startError = error instanceof DurableApiError ? error.message : 'Failed to start run';
    } finally {
      startingId = null;
    }
  }
</script>

<h1 class="govuk-heading-l">Start a workflow</h1>

{#if loadError}
  <p class="govuk-error-message">{loadError}</p>
{/if}

{#if startError}
  <p class="govuk-error-message">{startError}</p>
{/if}

<div class="workflow-list">
  {#each workflows as workflow (workflow.id)}
    <div class="ss-card">
      <span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-0">
        {workflow.name ?? workflow.id}
      </span>
      <button
        class="govuk-button ss-cta workflow-list__start govuk-!-margin-bottom-0"
        type="button"
        disabled={startingId === workflow.id}
        onclick={() => start(workflow.id)}
      >
        {startingId === workflow.id ? 'Starting…' : 'Start'}
      </button>
    </div>
  {:else}
    {#if !loadError}
      <p class="govuk-body ss-muted">No workflows registered on the workflow server.</p>
    {/if}
  {/each}
</div>

<style>
  .workflow-list {
    margin-top: 20px;
  }

  .workflow-list :global(.ss-card:first-child) {
    border-top: 1px solid #b1b4b6;
  }

  .workflow-list__start {
    margin-left: auto;
  }
</style>
