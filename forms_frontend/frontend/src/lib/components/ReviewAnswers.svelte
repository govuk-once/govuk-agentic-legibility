<script lang="ts">
  import { amendReview, confirmReview, type AcceptedAnswer, type SessionState } from "../api";
  import { submissionValue } from "../submissionValue.js";
  import { toggleSelectedValues, visibleSelectionOptions } from "../selectionOptions.js";
  import { formatReviewValue, initialReviewDraft } from "../reviewValues.js";

  interface Props {
    sessionId: string;
    state: SessionState;
    onStateChange: (updated: SessionState) => void;
    onComplete: () => void | Promise<void>;
  }
  let { sessionId, state: sessionState, onStateChange, onComplete }: Props = $props();
  let editing = $state(-1);
  let draft: any = $state("");
  let busy = $state(false);
  let error = $state("");
  const answers = $derived(sessionState.answer_history ?? []);
  const autoCount = $derived(answers.filter((a) => a.source === "auto").length);

  function startEdit(index: number) {
    const answer = answers[index];
    editing = index;
    error = "";
    draft = initialReviewDraft(answer);
  }

  function isOptional(answer: AcceptedAnswer): boolean {
    return answer.presentation?.is_optional ?? answer.schema.allow_skip ?? false;
  }

  async function saveEdit(index: number) {
    if (busy) return;
    const answer = answers[index];
    const prepared = submissionValue(draft, answer.schema, isOptional(answer));
    if (prepared.error) {
      error = prepared.error;
      return;
    }
    busy = true;
    error = "";
    try {
      const next = await amendReview(sessionId, index, answer.state_id,
        prepared.value, sessionState.review_revision);
      editing = -1;
      onStateChange(next);
    } catch (e: any) {
      error = e.message || "Your change could not be validated. Your original answers are unchanged.";
    } finally {
      busy = false;
    }
  }

  async function acceptAnswers() {
    if (busy || editing !== -1) return;
    busy = true;
    error = "";
    try {
      await confirmReview(sessionId);
      // The API has accepted the user's final approval.  Do not wait for the
      // underlying Temporal execution to move from its terminal EndState to a
      // transport-level CLOSED status before showing completion.
      onStateChange({ ...sessionState, review_confirmed: true, review_required: false });
    } catch (e: any) {
      error = e.message || "Unable to finish reviewing your answers";
    } finally {
      busy = false;
    }
  }
</script>

<h2 class="govuk-heading-l">Check your answers</h2>
<p class="govuk-body">
  Check all your answers and change anything that is incorrect before you accept them.
</p>
<p class="govuk-body-s" role="status">
  <strong>{answers.length} questions answered</strong>
  {#if autoCount > 0}
    ({autoCount} auto-filled, {answers.length - autoCount} entered or confirmed by you)
  {/if}
</p>

{#if error && editing === -1}
  <div class="govuk-error-summary" role="alert">
    <h3 class="govuk-error-summary__title">There is a problem</h3>
    <div class="govuk-error-summary__body">{error}</div>
  </div>
{/if}

<dl class="govuk-summary-list">
  {#each answers as answer, i}
    <div class="govuk-summary-list__row">
      <dt class="govuk-summary-list__key">{answer.presentation?.question_text || answer.question_text}</dt>
      <dd class="govuk-summary-list__value">
        {#if editing === i}
          <form onsubmit={(event) => { event.preventDefault(); void saveEdit(i); }}>
            <div class="govuk-form-group" class:govuk-form-group--error={!!error}>
              {#if error}
                <p class="govuk-error-message" role="alert">{error}</p>
              {/if}
              {#if answer.schema.kind === "boolean" || answer.schema.kind === "select_one"}
                <fieldset class="govuk-fieldset">
                  <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Change answer</legend>
                  <div class="govuk-radios govuk-radios--small">
                    {#each (answer.schema.kind === "boolean"
                      ? [{ value: "true", label: "Yes" }, { value: "false", label: "No" }]
                      : visibleSelectionOptions(answer.schema.options ?? [])) as option}
                      <div class="govuk-radios__item">
                        <input type="radio" class="govuk-radios__input"
                          id={`review-${i}-${option.value}`} name={`review-${i}`}
                          value={option.value} checked={draft === option.value}
                          onchange={() => (draft = option.value)} />
                        <label class="govuk-label govuk-radios__label" for={`review-${i}-${option.value}`}>
                          {option.label}
                        </label>
                      </div>
                    {/each}
                  </div>
                </fieldset>
              {:else if answer.schema.kind === "select_many"}
                <fieldset class="govuk-fieldset">
                  <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">Change answer</legend>
                  <div class="govuk-checkboxes govuk-checkboxes--small">
                    {#each answer.schema.options ?? [] as option}
                      <div class="govuk-checkboxes__item">
                        <input type="checkbox" class="govuk-checkboxes__input"
                          id={`review-${i}-${option.value}`} checked={Array.isArray(draft) && draft.includes(option.value)}
                          onchange={(e) => {
                            draft = toggleSelectedValues(draft, option.value,
                              e.currentTarget.checked, answer.schema.exclusive_options ?? []);
                          }} />
                        <label class="govuk-label govuk-checkboxes__label" for={`review-${i}-${option.value}`}>
                          {option.label}
                        </label>
                      </div>
                    {/each}
                  </div>
                </fieldset>
              {:else if answer.presentation?.answer_settings?.input_type === "long_text"}
                <label class="govuk-label" for={`review-${i}`}>Change answer</label>
                <textarea class="govuk-textarea" id={`review-${i}`} rows="4" bind:value={draft}></textarea>
              {:else}
                <label class="govuk-label" for={`review-${i}`}>Change answer</label>
                {#if answer.presentation?.answer_type === "date"}
                  <p class="govuk-hint">Enter day/month/year, for example 01/01/2026.</p>
                {:else if answer.presentation?.answer_type === "address"}
                  <p class="govuk-hint">Enter the full address, separated by commas.</p>
                {/if}
                {#if answer.presentation?.answer_type === "email"}
                  <input class="govuk-input" id={`review-${i}`} type="email" bind:value={draft} />
                {:else}
                  <input class={answer.presentation?.answer_type === "number"
                    ? "govuk-input govuk-input--width-10" : "govuk-input"}
                    id={`review-${i}`} type="text" bind:value={draft} />
                {/if}
              {/if}
              {#if isOptional(answer)}
                <p class="govuk-hint">Clear the answer to skip this question.</p>
              {/if}
            </div>
            <button type="submit" class="govuk-button govuk-!-margin-right-3" disabled={busy}>
              {busy ? "Checking change..." : "Save change"}
            </button>
            <button type="button" class="govuk-button govuk-button--secondary"
              disabled={busy} onclick={() => { editing = -1; error = ""; }}>Cancel</button>
          </form>
        {:else}
          {formatReviewValue(answer)}
        {/if}
      </dd>
      <dd class="govuk-summary-list__actions">
          {#if answer.source === "auto"}
            <span class="govuk-tag--blue govuk-!-margin-right-2">Auto-filled</span>
          {/if}
        {#if editing !== i && answer.schema.kind !== "file_ref"}
          <button type="button" class="govuk-link review-change"
            disabled={busy || editing !== -1} onclick={() => startEdit(i)}>
            Change <span class="govuk-visually-hidden">{answer.presentation?.question_text || answer.question_text}</span>
          </button>
        {/if}
      </dd>
    </div>
  {/each}
</dl>

<p class="govuk-body-s">This prototype collects answers but does not send them to a department.</p>
<button class="govuk-button" type="button" disabled={busy || editing !== -1}
  onclick={() => void acceptAnswers()}>
  {busy ? "Finishing..." : "Accept and continue"}
</button>

<style>
  .review-change { background: none; border: 0; padding: 0; cursor: pointer; font: inherit; }
  .review-change:disabled { color: #505a5f; cursor: default; }
</style>
