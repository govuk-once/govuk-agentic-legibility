<script lang="ts">
  // Shared (src/lib/agentic/preseed-examples.ts): the example facts written for each journey
  import { examplesFor } from '$lib/agentic/preseed-examples';

  interface Props {
    /** The journey chosen on the start screen, used to offer examples written for it. */
    workflowId: string;
    /** The facts typed in. Kept by the start screen and saved against the call when it starts. */
    notes: string;
    onclose: () => void;
  }

  let { workflowId, notes = $bindable(), onclose }: Props = $props();

  let exampleId = $state('');
  const examples = $derived(examplesFor(workflowId));

  function loadExample() {
    const example = examples.find((candidate) => candidate.id === exampleId);
    if (example) notes = example.build(new Date());
  }

  // Moves keyboard focus into the sheet when it opens, onto its heading, so a screen reader starts
  // reading there and Tab continues from it.
  function focusHeading(node: HTMLElement) {
    node.querySelector('h2')?.focus();
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape') onclose();
  }}
/>

<div aria-hidden="true"></div>
<div
  class="govuk-!-padding-4"
  role="dialog"
  aria-modal="true"
  aria-labelledby="mvi-context-title"
  {@attach focusHeading}
>
  <header>
    <h2 class="govuk-heading-m govuk-!-margin-0" id="mvi-context-title" tabindex="-1">
      What the service already knows
    </h2>
    <button
      type="button"
      class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
      aria-label="Close"
      onclick={onclose}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" focusable="false">
        <path
          d="M2 2L14 14M14 2L2 14"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="square"
        />
      </svg>
    </button>
  </header>

  <p class="govuk-body ss-muted govuk-!-margin-top-3">
    Stands in for what a real service might already know about the caller. Where it covers a question, the
    phone offers it as a suggested answer.
  </p>

  {#if examples.length > 0}
    <div class="govuk-form-group">
      <label class="govuk-label" for="mvi-example">Example facts</label>
      <select class="govuk-select govuk-!-width-full" id="mvi-example" bind:value={exampleId}>
        <option value="">Choose an example…</option>
        {#each examples as example (example.id)}
          <option value={example.id}>{example.title}</option>
        {/each}
      </select>
      <button
        type="button"
        class="govuk-button govuk-button--secondary govuk-!-margin-top-2 govuk-!-margin-bottom-0"
        disabled={!exampleId}
        onclick={loadExample}
      >
        Load example
      </button>
    </div>
  {/if}

  <div class="govuk-form-group">
    <label class="govuk-label" for="mvi-notes">Facts</label>
    <textarea class="govuk-textarea" id="mvi-notes" rows="3" bind:value={notes}></textarea>
  </div>

  <button
    type="button"
    class="govuk-button govuk-button--secondary govuk-!-width-full govuk-!-margin-bottom-0"
    onclick={onclose}
  >
    Save facts
  </button>
</div>

<style>
  /* The sheet slides over the bottom of the phone with the rest of the screen dimmed behind it,
     as in the design. The sheet scrolls if the phone is too short to show all of it. */
  div[aria-hidden='true'] {
    position: absolute;
    inset: 0;
    background-color: rgba(11, 12, 12, 0.62);
  }

  div[role='dialog'] {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    max-height: 92%;
    overflow-y: auto;
    background-color: #ffffff;
    border-top: 5px solid #0b0c0c;
  }

  /* The heading only takes focus so a screen reader starts there. It isn't a control, so it
     shouldn't show the browser's focus box. */
  h2:focus {
    outline: none;
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
</style>
