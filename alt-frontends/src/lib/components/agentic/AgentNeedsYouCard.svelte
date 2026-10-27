<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    /** Which question this is, for example 5 for "step 5". */
    step: number;
    /** Why the agent could not answer, in its own words. */
    reason?: string;
    /** Whether the agent carries on by itself once you have answered. */
    continueAfterAnswer: boolean;
    /** The question and its answer field. */
    children: Snippet;
  }

  let { step, reason, continueAfterAnswer = $bindable(), children }: Props = $props();
</script>

<section class="agent-needs-you govuk-!-margin-bottom-6" aria-labelledby="agent-needs-you-title">
  <header class="agent-needs-you__header">
    <span class="agent-needs-you__icon" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 16 16" focusable="false">
        <circle cx="8" cy="5" r="3" fill="none" stroke="#0b0c0c" stroke-width="1.5" />
        <path d="M2.5 14C3 10.5 13 10.5 13.5 14" fill="none" stroke="#0b0c0c" stroke-width="1.5" />
      </svg>
    </span>
    <div>
      <h2 id="agent-needs-you-title" class="govuk-heading-s govuk-!-margin-0">Waiting for you</h2>
      <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0 agent-needs-you__note">
        <span>step {step}</span>
        <span>needs a human</span>
      </p>
    </div>
  </header>

  <div class="agent-needs-you__card">
    {#if reason}
      <p class="govuk-body govuk-!-font-size-16 govuk-!-margin-bottom-3">{reason}</p>
    {/if}

    <div class="agent-needs-you__question">
      {@render children()}
    </div>

    <div class="govuk-checkboxes govuk-checkboxes--small">
      <div class="govuk-checkboxes__item">
        <input class="govuk-checkboxes__input" id="continue-after-answer" type="checkbox" bind:checked={continueAfterAnswer} />
        <label class="govuk-label govuk-checkboxes__label" for="continue-after-answer">
          Carry on autonomously after I answer
        </label>
      </div>
    </div>
  </div>
</section>

<style>
  .agent-needs-you__header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
  }

  /* A small yellow square holding a person, to show this one is for a human. */
  .agent-needs-you__icon {
    display: flex;
    flex: 0 0 36px;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background-color: #fff7bf;
  }

  /* The note is set in a fixed-width typeface, with its two parts side by side. */
  .agent-needs-you__note {
    display: flex;
    gap: 12px;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
  }

  .agent-needs-you__card {
    padding: 20px;
    border: 1px solid #b1b4b6;
    border-radius: 12px;
  }

  /* The question is the large heading of the answer field. KindField is shared with other pages,
     so its text is sized from here instead of changing the component. */
  .agent-needs-you__question :global(.govuk-fieldset__legend) {
    font-size: 1.5rem;
    font-weight: 700;
  }

  .agent-needs-you__question :global(.govuk-form-group) {
    margin-bottom: 10px;
  }

  /* Space between the answer field and the Continue button. */
  .agent-needs-you__question :global(.govuk-button) {
    margin-top: 20px;
  }
</style>
