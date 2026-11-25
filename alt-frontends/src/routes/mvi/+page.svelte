<script lang="ts">
  import { goto } from '$app/navigation';
  // Shared (src/lib/api/client.ts): lists the journeys, starts a run and saves the facts against it
  import { DurableApiError, listWorkflows, saveWebContext, startRun } from '$lib/api/client';
  // Shared (src/lib/types.ts): the journey summary type
  import type { WorkflowSummary } from '$lib/types';
  import ContextSheet from '$lib/mvi/ContextSheet.svelte';
  import PhoneShell from '$lib/mvi/PhoneShell.svelte';

  let workflows: WorkflowSummary[] = $state([]);
  let selectedId = $state('');
  let loadError: string | null = $state(null);
  let startError: string | null = $state(null);
  let starting = $state(false);

  // Facts typed into the add-context sheet. They are saved against the call once it starts.
  let notes = $state('');
  let sheetOpen = $state(false);

  $effect(() => {
    listWorkflows()
      .then((result) => {
        workflows = result;
        if (!selectedId && result.length > 0) selectedId = result[0].id;
      })
      .catch((error: unknown) => {
        loadError = error instanceof DurableApiError ? error.message : 'Failed to load workflows';
      });
  });

  async function start() {
    if (!selectedId || starting) return;
    startError = null;
    starting = true;
    try {
      const { workflow_id } = await startRun(selectedId);
      if (notes.trim()) {
        try {
          await saveWebContext(workflow_id, notes);
        } catch {
          // Suggestions are optional, so the call still starts without them.
        }
      }
      await goto(`/mvi/${encodeURIComponent(workflow_id)}`);
    } catch (error) {
      startError = error instanceof DurableApiError ? error.message : 'Failed to start the call';
    } finally {
      starting = false;
    }
  }
</script>

<PhoneShell top>
  <fieldset class="govuk-fieldset">
    <legend class="govuk-fieldset__legend govuk-visually-hidden">Choose a journey</legend>

    {#if loadError}
      <p class="govuk-error-message">{loadError}</p>
    {/if}
    {#if startError}
      <p class="govuk-error-message">{startError}</p>
    {/if}

    <div class="govuk-radios" data-module="govuk-radios">
      {#each workflows as workflow, index (workflow.id)}
        <div class="ss-panel govuk-!-margin-bottom-3">
          <div class="govuk-radios__item govuk-!-margin-bottom-0">
            <input
              class="govuk-radios__input"
              id={`mvi-journey-${index}`}
              name="journey"
              type="radio"
              value={workflow.id}
              bind:group={selectedId}
            />
            <label class="govuk-label govuk-radios__label govuk-!-font-weight-bold" for={`mvi-journey-${index}`}>
              {workflow.name ?? workflow.id}
            </label>
          </div>
        </div>
      {:else}
        {#if !loadError}
          <p class="govuk-body ss-muted">No workflows registered on the workflow server.</p>
        {/if}
      {/each}
    </div>
  </fieldset>

  {#snippet actions()}
    <button
      type="button"
      class="govuk-button govuk-button--secondary govuk-!-width-full govuk-!-margin-bottom-3"
      onclick={() => (sheetOpen = true)}
    >
      <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" focusable="false">
        <path d="M9 2V16M2 9H16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="square" />
      </svg>
      {notes.trim() ? 'Edit context' : 'Add context'}
    </button>
    <button
      type="button"
      class="govuk-button govuk-button--start govuk-!-width-full govuk-!-margin-bottom-0"
      disabled={!selectedId || starting}
      onclick={start}
    >
      {starting ? 'Starting…' : 'Start now'}
      <svg
        class="govuk-button__start-icon"
        xmlns="http://www.w3.org/2000/svg"
        width="17.5"
        height="19"
        viewBox="0 0 33 40"
        aria-hidden="true"
        focusable="false"
      >
        <path fill="currentColor" d="M0 0h13l20 20-20 20H0l20-20z" />
      </svg>
    </button>
  {/snippet}

  {#snippet overlay()}
    {#if sheetOpen}
      <ContextSheet workflowId={selectedId} bind:notes onclose={() => (sheetOpen = false)} />
    {/if}
  {/snippet}
</PhoneShell>

<style>
  /* The chosen journey gets a thick black border, as in the design. The padding comes down by the
     same amount so the card doesn't change size when it is chosen. */
  .ss-panel:has(input:checked) {
    border: 3px solid #0b0c0c;
    padding: 18px;
  }
</style>
