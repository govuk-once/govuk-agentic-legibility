<script lang="ts">
  // Shared (src/lib/mvi/format.ts): turns a journey id such as "dvla.change_of_address" into a readable name
  import { describeWorkflow } from '$lib/mvi/format';
  import type { ActiveWorkflowSummary } from '$lib/types';

  let {
    workflows,
    selectedId = null,
    onresume
  }: {
    workflows: ActiveWorkflowSummary[];
    /** The run the page is on, shown highlighted. */
    selectedId?: string | null;
    onresume: (workflowId: string) => void;
  } = $props();

  // Only the first few runs show up front. The rest sit in a "Show more" details box.
  const VISIBLE_RUNS = 4;
  // The run the page is on goes first, as long as it is still running.
  const ordered = $derived.by(() => {
    const current = workflows.find((w) => w.id === selectedId && w.status.toUpperCase() === 'RUNNING');
    return current ? [current, ...workflows.filter((w) => w !== current)] : workflows;
  });
  const visible = $derived(ordered.slice(0, VISIBLE_RUNS));
  const hidden = $derived(ordered.slice(VISIBLE_RUNS));

  // A run id looks like "sfsm-dvla.change_of_address-8537ccb0": the journey id with a prefix and
  // a short random ending. Anything that doesn't look like that is shown as it is.
  function runName(id: string): string {
    const journeyId = id.replace(/^sfsm-/, '').replace(/-[0-9a-f]{8}$/, '');
    return journeyId.includes('.') ? describeWorkflow(journeyId).journey : id;
  }

  // "RUNNING" becomes "Running".
  function statusText(status: string): string {
    return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
  }
</script>

{#snippet run(workflow: ActiveWorkflowSummary)}
  {@const selected = workflow.id === selectedId}
  <li class="run-picker__item">
    <button
      type="button"
      class="run-picker__run govuk-body govuk-!-font-size-19 govuk-!-margin-0"
      class:run-picker__run--selected={selected}
      aria-current={selected ? 'true' : undefined}
      title={workflow.id}
      onclick={() => onresume(workflow.id)}
    >
      <span class:govuk-!-font-weight-bold={selected}>{runName(workflow.id)}</span>
      <span class="run-picker__status ss-muted">{statusText(workflow.status)}</span>
    </button>
  </li>
{/snippet}

{#if workflows.length > 0}
  <section aria-labelledby="run-picker-heading">
    <div class="run-picker__heading">
      <h2 id="run-picker-heading" class="govuk-body govuk-!-font-size-19 govuk-!-font-weight-bold govuk-!-margin-0">
        Resume an active chat
      </h2>
      <span class="govuk-body govuk-!-font-size-19 govuk-!-margin-0 ss-muted">{workflows.length}</span>
    </div>
    <ul class="govuk-list govuk-!-margin-0">
      {#each visible as workflow (workflow.id)}
        {@render run(workflow)}
      {/each}
    </ul>
    {#if hidden.length > 0}
      <details class="govuk-details govuk-!-margin-top-2" data-module="govuk-details">
        <summary class="govuk-details__summary">
          <span class="govuk-details__summary-text">Show {hidden.length} more</span>
        </summary>
        <div class="govuk-details__text govuk-!-padding-0 run-picker__more">
          <ul class="govuk-list govuk-!-margin-0">
            {#each hidden as workflow (workflow.id)}
              {@render run(workflow)}
            {/each}
          </ul>
        </div>
      </details>
    {/if}
  </section>
{/if}

<style>
  .run-picker__heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 0 8px 8px;
  }

  .run-picker__item + .run-picker__item {
    margin-top: 6px;
  }

  .run-picker__run {
    display: block;
    width: 100%;
    padding: 10px 12px 10px 15px;
    border: 0;
    background: none;
    text-align: left;
    cursor: pointer;
  }

  .run-picker__run:hover {
    background-color: #f3f2f1;
  }

  .run-picker__run:focus-visible {
    outline: 3px solid #ffdd00;
  }

  /* The run the chat is on: grey background with a blue edge on the left, rounded on the right. */
  .run-picker__run--selected {
    padding-left: 12px;
    border-left: 3px solid #1d70b8;
    border-radius: 0 8px 8px 0;
    background-color: #f3f2f1;
  }

  /* The runs under "Show more" line up with the rest, without the details box's grey left edge. */
  .run-picker__more {
    border-left: 0;
  }

  .run-picker__status {
    display: block;
    padding-top: 2px;
  }
</style>
