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
  // Shared (src/lib/mvi/format.ts): turns a journey id such as "dvla.change_of_address" into a readable name
  import { describeWorkflow } from '$lib/mvi/format';
  import type { AwaitingInput, PrefillSuggestion, RunEvent } from '$lib/types';

  const workflowId = page.params.workflowId!;

  // A run id looks like "sfsm-dvla.change_of_address-8537ccb0": the journey id with a prefix and a
  // short random ending. Anything that doesn't look like that is shown as it is.
  const journeyName = (() => {
    const journeyId = workflowId.replace(/^sfsm-/, '').replace(/-[0-9a-f]{8}$/, '');
    return journeyId.includes('.') ? describeWorkflow(journeyId).journey : workflowId;
  })();

  interface TranscriptLine {
    role: string;
    text: string;
  }

  let transcript: TranscriptLine[] = $state([]);
  let awaiting: AwaitingInput | null = $state(null);
  let status: string | null = $state(null);
  let submitError: string | null = $state(null);
  let submitting = $state(false);

  // The questions answered on this page, in order. The question number comes from this, and so
  // will the progress list. It starts empty when the page is reloaded.
  let answered: { token: string; prompt: string }[] = $state([]);
  const questionNumber = $derived(answered.length + 1);

  // Messages from the service that came after the last answer. The question itself is left out,
  // because it is shown in the question card.
  let messagesFrom = $state(0);
  const messages = $derived(transcript.slice(messagesFrom).filter((line) => line.text !== awaiting?.prompt));

  // Optional, opt-in LLM pre-fill (see prefill-prompt.ts): the executor
  // above stays the sole source of truth and validator — this only ever
  // seeds a suggested value into KindField for the user to review or edit.
  let notesDraft = $state('');
  let hasContext = $state(false);
  let notesSaved = $state(false);
  // Whether the Add context panel is open in the side column.
  let contextOpen = $state(false);
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
      answered = [...answered, { token: awaiting.token, prompt: awaiting.prompt }];
      messagesFrom = transcript.length;
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
      contextOpen = false;
      lastSuggestedToken = null;
      void fetchSuggestion();
    } catch {
      // Non-fatal: pre-fill is advisory, the deterministic form still works.
      notesSaved = false;
    }
  }
</script>

<div class="web-page">
<div class="govuk-grid-row">
  <div class="govuk-grid-column-two-thirds">
<h1 class="govuk-visually-hidden">{journeyName}</h1>

{#if awaiting}
  <p class="govuk-body ss-muted govuk-!-margin-bottom-4">{journeyName} · Question {questionNumber}</p>
{/if}

{#each messages as line, index (index)}
  <p class="govuk-body">{line.text}</p>
{/each}

{#if submitError}
  <p class="govuk-error-message">{submitError}</p>
{/if}

{#if suggestionLoading}
  <p class="govuk-body ss-muted">Checking your notes for a suggestion…</p>
{/if}

{#if awaiting}
  <div class="web-question">
    <fieldset disabled={submitting}>
      <KindField {awaiting} onsubmit={handleSubmit} {suggestion} />
    </fieldset>
  </div>
{:else if status && status !== 'RUNNING'}
  <p class="govuk-body">This run has finished.</p>
{/if}
  </div>

  <div class="govuk-grid-column-one-third">
    <!-- The questions answered so far, then the one being asked. Questions still to come aren't known,
         because the journey branches on the answers. -->
    <section class="web-side" aria-labelledby="web-progress-heading">
      <h2 id="web-progress-heading" class="govuk-heading-s web-side__heading">Your progress</h2>
      <ul class="govuk-list govuk-!-margin-0">
        {#each answered as step (step.token)}
          <li class="ss-card web-step">
            <svg class="web-step__icon" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <circle cx="12" cy="12" r="12" fill="#00703c" />
              <path d="M6.5 12.5L10.3 16L17.5 8" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="govuk-body govuk-!-margin-0">{step.prompt}</span>
          </li>
        {/each}
        {#if awaiting}
          <li class="ss-card web-step" aria-current="step">
            <svg class="web-step__icon" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <circle cx="12" cy="12" r="12" fill="#ffdd00" />
              <path d="M12 6.5V13M12 16.5V17.5" fill="none" stroke="#0b0c0c" stroke-width="2.4" stroke-linecap="round" />
            </svg>
            <span class="govuk-body govuk-!-margin-0">{awaiting.prompt}</span>
          </li>
        {/if}
      </ul>
    </section>

    <section class="web-side govuk-!-margin-top-6" aria-labelledby="web-settings-heading">
      {#if contextOpen}
        <div class="web-side__heading web-side__heading--row">
          <h2 id="web-settings-heading" class="govuk-heading-s govuk-!-margin-0">Add context</h2>
          {#if notesSaved}
            <strong class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 web-saved">Notes saved</strong>
          {/if}
        </div>
        <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-top-3 govuk-!-margin-bottom-3">
          An LLM uses your notes to suggest a value for each question. You always review the
          suggestion before continuing.
        </p>
        <div class="govuk-form-group govuk-!-margin-bottom-3">
          <label class="govuk-label govuk-!-font-size-16" for="web-context-notes">Your notes</label>
          <textarea
            class="govuk-textarea govuk-!-margin-bottom-0"
            id="web-context-notes"
            rows="4"
            bind:value={notesDraft}
          ></textarea>
        </div>
        <button type="button" class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" onclick={handleSaveNotes}>
          Save notes
        </button>
      {:else}
        <h2 id="web-settings-heading" class="govuk-heading-s web-side__heading">Your settings</h2>
        <div class="ss-card web-setting">
          <div>
            <span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-0">Add context</span>
            <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 ss-muted web-setting__note">
              {notesSaved ? 'Notes saved.' : 'No notes saved.'}
            </span>
          </div>
          <a
            href="#web-context-notes"
            class="govuk-link web-setting__action"
            onclick={(event) => {
              event.preventDefault();
              contextOpen = true;
            }}
          >
            {notesSaved ? 'Edit notes' : 'Add notes'}
          </a>
        </div>
      {/if}
    </section>

    <section class="web-side govuk-!-margin-top-6" aria-labelledby="web-help-heading">
      <h2 id="web-help-heading" class="govuk-heading-s web-side__heading">Help</h2>
      <p class="govuk-body govuk-!-margin-top-3 govuk-!-margin-bottom-0">
        <a class="govuk-link" href="https://www.gov.uk">Find help on GOV.UK</a>
      </p>
    </section>

    {#if status}
      <p class="govuk-body govuk-!-margin-top-6">
        <strong class="govuk-tag {status === 'RUNNING' ? 'govuk-tag--green' : 'govuk-tag--grey'}">
          {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()}
        </strong>
        <span class="ss-muted govuk-!-margin-left-2">{workflowId.slice(-8)}</span>
      </p>
    {/if}
  </div>
</div>
</div>

<style>
  /* The two columns are a grid instead of the floats gov.css uses. With floats, the right column
     slides to the left edge whenever the left one is empty, which happens for a moment each time an
     answer is sent. */
  @media (min-width: 40.0625em) {
    .web-page :global(.govuk-grid-row) {
      display: grid;
      grid-template-columns: 2fr 1fr;
    }

    .web-page :global(.govuk-grid-row::after) {
      display: none;
    }

    .web-page :global(.govuk-grid-column-two-thirds),
    .web-page :global(.govuk-grid-column-one-third) {
      float: none;
      width: auto;
      min-width: 0;
    }
  }

  /* Text boxes and buttons here have rounded corners and no bottom edge, as in the design. */
  .web-page :global(.govuk-input),
  .web-page :global(.govuk-textarea) {
    border-radius: 8px;
  }

  .web-page :global(.govuk-button) {
    border-radius: 8px;
    box-shadow: none;
  }

  /* The question card. The question is set at the size of a large GOV.UK heading, and the answer
     options are boxes with rounded corners. KindField is shared with /agentic, so these are
     reached from here with :global instead of changing the component. */
  .web-question :global(.govuk-fieldset__legend) {
    font-size: 2.25rem;
    line-height: 1.1111111111;
    font-weight: 700;
  }

  /* The browser draws a grey box around the disabled-while-sending fieldset, so that is removed. */
  .web-question > fieldset {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }

  /* Each option sits in a rounded box. The radio's circle and dot are drawn by gov.css from the
     box's corner, so they are moved in by the same amount as the padding. */
  .web-question :global(.govuk-radios__item) {
    margin-bottom: 12px;
    padding: 4px 8px;
    /* border: 1px solid #b1b4b6; */
    border-radius: 8px;
  }

  .web-question :global(.govuk-radios__label::before) {
    top: 6px;
    left: 10px;
  }

  .web-question :global(.govuk-radios__label::after) {
    top: 16px;
    left: 20px;
  }

  /* Space between the answer options and the Continue button. */
  .web-question :global(.govuk-button) {
    margin-top: 20px;
  }

  /* The right-hand sections each start with a heading underlined in blue. */
  .web-side__heading {
    margin-bottom: 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #1d70b8;
  }

  .web-step {
    align-items: flex-start;
    gap: 12px;
    padding: 12px 0;
  }

  /* "Notes saved" is plain green text next to the heading, not a tag. */
  .web-saved {
    color: #005a30;
  }

  /* The grey Save notes button has a thin grey outline, as in the design. */
  .web-page :global(.govuk-button--secondary) {
    border: 1px solid #b1b4b6;
  }

  .web-side__heading--row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }

  .web-setting {
    padding: 10px 0;
  }

  .web-setting__note {
    display: block;
  }

  .web-setting__action {
    margin-left: auto;
  }

  .web-step__icon {
    flex: 0 0 24px;
  }
</style>
