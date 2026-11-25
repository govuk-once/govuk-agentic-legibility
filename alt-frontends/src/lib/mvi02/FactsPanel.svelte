<script lang="ts">
  // Shared (src/lib/agentic/preseed-examples.ts): the example facts written for each journey
  import { examplesFor } from '$lib/agentic/preseed-examples';
  import Icon from './Icon.svelte';
  import RadioCard from './RadioCard.svelte';

  interface Props {
    /** The journey chosen on the start screen, used to offer examples written for it. */
    workflowId: string;
    /** The facts. Kept by the start screen and passed to the agent when the call starts. */
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

  // Moves keyboard focus into the panel when it opens, onto its heading.
  function focusHeading(node: HTMLElement) {
    node.querySelector('h2')?.focus();
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape') onclose();
  }}
/>

<div class="mvi2-scrim" aria-hidden="true"></div>
<div class="mvi2-panel" role="dialog" aria-modal="true" aria-labelledby="mvi2-facts-title" {@attach focusHeading}>
  <div class="mvi2-panel__head">
    <h2 id="mvi2-facts-title" tabindex="-1">What the service already knows</h2>
    <button type="button" class="mvi2-close" aria-label="Close" onclick={onclose}>
      <Icon name="close" />
    </button>
  </div>
  <p>Facts about you that I can offer as suggested answers.</p>

  {#if examples.length > 0}
    <h3 id="mvi2-examples-label">Example facts</h3>
    <div class="mvi2-stack" role="radiogroup" aria-labelledby="mvi2-examples-label">
      {#each examples as example (example.id)}
        <RadioCard
          name="mvi2-example"
          value={example.id}
          bind:group={exampleId}
          label={example.title}
          hint={example.description}
          size="compact"
        />
      {/each}
    </div>
  {/if}

  <h3><label for="mvi2-facts">Facts</label></h3>
  <textarea class="mvi2-facts" id="mvi2-facts" rows="5" bind:value={notes}></textarea>

  <div class="mvi2-panel__actions">
    {#if examples.length > 0}
      <button type="button" class="mvi2-btn" disabled={!exampleId} onclick={loadExample}>
        Load into chat
        <Icon name="arrow" width={16} height={13} color="#12E2F7" />
      </button>
    {/if}
    <button type="button" class="mvi2-btn mvi2-btn--outline" onclick={onclose}>Save facts</button>
  </div>
</div>
