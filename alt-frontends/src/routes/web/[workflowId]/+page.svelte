<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/state';
  import { onDestroy } from 'svelte';
  import {
    DurableApiError,
    getPrefillSuggestion,
    getRunState,
    saveWebContext,
    submitRunInput
  } from '$lib/api/client';
  import { watchRun } from '$lib/api/sse';
  import KindField from '$lib/components/forms/KindField.svelte';
  import type { AwaitingInput, PrefillSuggestion, RunEvent } from '$lib/types';

  const workflowId = page.params.workflowId!;

  interface TranscriptLine {
    role: string;
    text: string;
  }

  let transcript: TranscriptLine[] = $state([]);
  let awaiting: AwaitingInput | null = $state(null);
  let status: string | null = $state(null);
  let submitError: string | null = $state(null);
  let submitting = $state(false);

  // Optional, opt-in LLM pre-fill (see prefill-prompt.ts): the executor
  // above stays the sole source of truth and validator — this only ever
  // seeds a suggested value into KindField for the user to review or edit.
  let notesDraft = $state('');
  let hasContext = $state(false);
  let notesSaved = $state(false);
  let suggestion: PrefillSuggestion | null = $state(null);
  let suggestionLoading = $state(false);
  let lastSuggestedToken: string | null = null;

  async function refreshAwaiting() {
    try {
      const state = await getRunState(workflowId);
      awaiting = state.awaiting;
      status = state.status;
    } catch (error) {
      submitError = error instanceof DurableApiError ? error.message : 'Failed to load run state';
    }
  }

  async function fetchSuggestion() {
    if (!awaiting || !hasContext) {
      suggestion = null;
      return;
    }
    if (lastSuggestedToken === awaiting.token) return;
    lastSuggestedToken = awaiting.token;
    suggestionLoading = true;
    try {
      suggestion = await getPrefillSuggestion(workflowId, awaiting);
    } catch {
      suggestion = null;
    } finally {
      suggestionLoading = false;
    }
  }

  $effect(() => {
    void fetchSuggestion();
  });

  function handleEvent(event: RunEvent) {
    if (event.type === 'message' && event.text) {
      transcript = [...transcript, { role: event.role ?? 'assistant', text: event.text }];
    } else if (event.type === 'options') {
      // The SSE options event carries kind/choices but not the field's
      // token, so re-fetch the authoritative state to get a submittable
      // AwaitingInput (see agent/api/events.py:RunEvent — token is only
      // used internally to dedupe, never broadcast).
      void refreshAwaiting();
    } else if (event.type === 'completed') {
      status = event.status ?? 'COMPLETED';
      awaiting = null;
      stopWatching();
    }
  }

  // EventSource only exists in the browser; SSR renders without the live feed.
  const stopWatching = browser ? watchRun(workflowId, handleEvent) : () => {};
  onDestroy(stopWatching);

  async function handleSubmit(value: unknown) {
    if (!awaiting) return;
    submitError = null;
    submitting = true;
    try {
      await submitRunInput(workflowId, awaiting.token, value);
      awaiting = null;
    } catch (error) {
      submitError = error instanceof DurableApiError ? error.message : 'Failed to submit input';
    } finally {
      submitting = false;
    }
  }

  async function handleSaveNotes() {
    try {
      await saveWebContext(workflowId, notesDraft);
      hasContext = notesDraft.trim().length > 0;
      notesSaved = true;
      lastSuggestedToken = null;
      void fetchSuggestion();
    } catch {
      // Non-fatal: pre-fill is advisory, the deterministic form still works.
      notesSaved = false;
    }
  }
</script>

<h1 class="govuk-heading-l">Run {workflowId}</h1>

{#if status}
  <p class="govuk-body">Status: <strong>{status}</strong></p>
{/if}

<div class="govuk-!-margin-bottom-6">
  {#each transcript as line, index (index)}
    <p class="govuk-body">{line.text}</p>
  {/each}
</div>

{#if submitError}
  <p class="govuk-error-message">{submitError}</p>
{/if}

<details class="govuk-details govuk-!-margin-bottom-6" data-module="govuk-details">
  <summary class="govuk-details__summary">
    <span class="govuk-details__summary-text">Speed this up</span>
  </summary>
  <div class="govuk-details__text">
    <div class="ss-panel">
      <p class="govuk-body ss-muted">
        Paste any notes or context you already have (an email, a case summary, previous
        answers). An LLM will use them to suggest a value for each question — you always
        review the suggestion and can edit or ignore it before continuing.
      </p>
      <div class="govuk-form-group">
        <label class="govuk-label" for="web-context-notes">Your notes</label>
        <textarea
          class="govuk-textarea"
          id="web-context-notes"
          rows="6"
          bind:value={notesDraft}
        ></textarea>
      </div>
      <button
        type="button"
        class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
        onclick={handleSaveNotes}
      >
        Save notes
      </button>
      {#if notesSaved}
        <p class="govuk-body ss-muted govuk-!-margin-top-2 govuk-!-margin-bottom-0">
          Notes saved. Suggestions will now be offered for each question.
        </p>
      {/if}
    </div>
  </div>
</details>

{#if suggestionLoading}
  <p class="govuk-body ss-muted">Checking your notes for a suggestion…</p>
{/if}

{#if awaiting}
  <fieldset disabled={submitting}>
    <KindField {awaiting} onsubmit={handleSubmit} {suggestion} />
  </fieldset>
{:else if status && status !== 'RUNNING'}
  <p class="govuk-body">This run has finished.</p>
{/if}
