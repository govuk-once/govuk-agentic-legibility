<script lang="ts">
  import type { AssistanceResponse } from '$lib/types';

  export let message = '';
  export let response: AssistanceResponse | null = null;
  export let error = '';
  export let disabled = false;
  export let requesting = false;
  export let onRequest: () => void;

  $: actions = response?.actions ?? [];
  $: noSafeSuggestion =
    actions.find((action) => action.type === 'no_safe_suggestion') ?? null;
  $: journeyAnswer =
    actions.find((action) => action.type === 'answer_journey_question') ?? null;
  $: retrievedGuidance = response?.retrieved_guidance ?? [];

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onRequest();
  }
</script>

<section class="assistant" aria-labelledby="assistant-heading">
  <div class="heading">
    <div>
      <span>Conversation context</span>
      <h3 id="assistant-heading">Ask or add information</h3>
    </div>
    <strong>Agent cannot continue the journey</strong>
  </div>
  <p>
    Ask a question about this step, add missing information or correct something in the
    conversation. The journey stays on the current form until you submit it.
  </p>

  <form onsubmit={submit}>
    <label for="assistant-message">Question or new information</label>
    <textarea
      id="assistant-message"
      rows="3"
      bind:value={message}
      placeholder="For example: Should I use postcode lookup if I live in a flat?"
      disabled={disabled || requesting}
    ></textarea>
    <button type="submit" disabled={disabled || requesting || !message.trim()}>
      {requesting ? 'Checking…' : 'Send to agent'}
    </button>
  </form>

  {#if error}
    <div class="error" role="alert"><strong>Agent assistance failed</strong><span>{error}</span></div>
  {:else if noSafeSuggestion}
    <div class="notice" role="status">
      <strong>No safe suggestion</strong>
      <span>{noSafeSuggestion.message}</span>
    </div>
  {:else if journeyAnswer}
    <div class="answer" role="status">
      <strong>Journey guidance</strong>
      <p>{journeyAnswer.answer}</p>
      {#if retrievedGuidance.length > 0}
        <span>
          Retrieved from:
          {retrievedGuidance.map((item) => item.title).join(', ')}
        </span>
      {:else}
        <span class="ungrounded">No approved journey guidance was retrieved for this answer.</span>
      {/if}
    </div>
  {/if}
</section>

<style>
  .assistant { margin: 2rem 0 0; border-top: 1px solid #b1b4b6; background: #f3f2f1; padding: 1rem 1.1rem 1.15rem; }
  .heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
  .heading span { color: #1d70b8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  .heading h3 { margin: .15rem 0 0; font-size: 1.12rem; line-height: 1.25; }
  .heading > strong { max-width: 12rem; border: 1px solid #1d70b8; color: #1d70b8; padding: .25rem .45rem; font-size: .68rem; line-height: 1.25; text-align: center; }
  .assistant > p { margin: .65rem 0 1rem; color: #505a5f; font-size: .9rem; }
  form { display: grid; gap: .55rem; }
  label { font-weight: 700; }
  textarea { width: 100%; resize: vertical; border: 2px solid #0b0c0c; background: #fff; padding: .65rem; font: inherit; line-height: 1.4; }
  textarea:focus, button:focus { outline: .2rem solid #ffdd00; outline-offset: 0; box-shadow: inset 0 0 0 2px #0b0c0c; }
  button { justify-self: start; border: 2px solid #0b0c0c; background: #fff; color: #0b0c0c; padding: .55rem .8rem; font: inherit; font-weight: 700; cursor: pointer; }
  button:hover:not(:disabled) { background: #e8f1f8; }
  button:disabled { cursor: wait; opacity: .55; }
  .notice, .answer, .error { display: grid; gap: .2rem; margin-top: 1rem; background: #fff; padding: .8rem .9rem; }
  .notice { border-left: .3rem solid #f47738; }
  .answer { border-left: .3rem solid #1d70b8; }
  .error { border-left: .3rem solid #d4351c; }
  .answer p { margin: .35rem 0; line-height: 1.45; }
  .notice span, .answer span, .error span { color: #505a5f; font-size: .86rem; }
  .answer .ungrounded { color: #d4351c; font-weight: 700; }
  @media (max-width: 38rem) { .heading { flex-direction: column; } .heading > strong { max-width: none; } }
</style>
