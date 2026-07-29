<script lang="ts">
  import type { AssistanceResponse } from '$lib/types';

  export let message = '';
  export let response: AssistanceResponse | null = null;
  export let error = '';
  export let disabled = false;
  export let requesting = false;
  export let onRequest: () => void;

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onRequest();
  }
</script>

<section class="assistant" aria-labelledby="assistant-heading">
  <div class="heading">
    <div>
      <span>Optional agent assistance</span>
      <h3 id="assistant-heading">Describe your answer in your own words</h3>
    </div>
    <strong>Agent cannot continue the journey</strong>
  </div>
  <p>
    The agent can suggest values for the current fields. You will still review the form
    and choose whether to continue.
  </p>

  <form onsubmit={submit}>
    <label for="assistant-message">Your message</label>
    <textarea
      id="assistant-message"
      rows="4"
      bind:value={message}
      placeholder="Tell us what you know about the information requested above."
      disabled={disabled || requesting}
    ></textarea>
    <button type="submit" disabled={disabled || requesting || !message.trim()}>
      {requesting ? 'Getting suggestion…' : 'Suggest values'}
    </button>
  </form>

  {#if error}
    <div class="error" role="alert"><strong>Agent assistance failed</strong><span>{error}</span></div>
  {:else if response?.action.type === 'propose_values'}
    <div class="proposal" role="status">
      <strong>Suggested values have been added to the form</strong>
      <span>Check or change them before continuing.</span>
      <dl>
        {#each Object.entries(response.action.values) as [name, value]}
          <div><dt>{name}</dt><dd>{String(value ?? '')}</dd></div>
        {/each}
      </dl>
    </div>
  {:else if response?.action.type === 'no_safe_suggestion'}
    <div class="notice" role="status">
      <strong>No safe suggestion</strong>
      <span>{response.action.message}</span>
    </div>
  {/if}
</section>

<style>
  .assistant { margin: 1.6rem 0 0; border: 1px solid #b1b4b6; border-left: .35rem solid #1d70b8; background: #f3f2f1; padding: 1rem 1.1rem 1.15rem; }
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
  .proposal, .notice, .error { display: grid; gap: .2rem; margin-top: 1rem; background: #fff; padding: .8rem .9rem; }
  .proposal { border-left: .3rem solid #00703c; }
  .notice { border-left: .3rem solid #f47738; }
  .error { border-left: .3rem solid #d4351c; }
  .proposal span, .notice span, .error span { color: #505a5f; font-size: .86rem; }
  dl { margin: .6rem 0 0; }
  dl div { display: grid; grid-template-columns: minmax(8rem,1fr) minmax(0,2fr); gap: .75rem; border-top: 1px solid #b1b4b6; padding: .35rem 0; font-size: .78rem; }
  dt { font-family: ui-monospace, monospace; }
  dd { margin: 0; overflow-wrap: anywhere; }
  @media (max-width: 38rem) { .heading { flex-direction: column; } .heading > strong { max-width: none; } }
</style>
