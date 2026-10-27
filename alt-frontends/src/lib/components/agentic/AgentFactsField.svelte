<script lang="ts">
  // Shared (src/lib/agentic/preseed-examples.ts): the example facts written for each journey
  import { examplesFor, type PreseedExample } from '$lib/agentic/preseed-examples';

  interface Props {
    /** Workflow definition id, used to offer only the examples written for it. */
    workflowId: string;
    value: string;
    /** Called when an example is loaded, so the page can apply its suggested policy. */
    onexample?: (example: PreseedExample) => void;
  }

  let { workflowId, value = $bindable(''), onexample }: Props = $props();

  let examples = $derived(examplesFor(workflowId));
  let selectedExampleId = $state('');
  let selectedExample = $derived(examples.find((example) => example.id === selectedExampleId));

  function loadExample() {
    if (!selectedExample) return;
    value = selectedExample.build(new Date());
    onexample?.(selectedExample);
  }
</script>

<div class="agent-facts">
  <label class="govuk-label govuk-label--s" for="agent-facts-text">Pre-seeded facts</label>
  <div id="agent-facts-hint" class="govuk-hint govuk-!-font-size-16">
    Anything the agent should know before it starts: names, dates, answers to yes or no questions. It answers
    from these facts and the profile bundle, and asks you only when neither covers it.
  </div>

  {#if examples.length}
    <div class="agent-facts__examples">
      <select class="govuk-select agent-facts__example-select" aria-label="Example facts" bind:value={selectedExampleId}>
        <option value="">Choose an example…</option>
        {#each examples as example (example.id)}
          <option value={example.id}>{example.title}</option>
        {/each}
      </select>
      <button
        class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
        type="button"
        disabled={!selectedExample}
        onclick={loadExample}
      >
        Load example
      </button>
    </div>
    {#if selectedExample}
      <p class="govuk-hint govuk-!-font-size-16 govuk-!-margin-bottom-3">
        {selectedExample.description} Loading it also sets the autonomy policy the example needs.
      </p>
    {/if}
  {/if}

  <textarea
    class="govuk-textarea agent-facts__text"
    id="agent-facts-text"
    rows="10"
    aria-describedby="agent-facts-hint"
    bind:value
  ></textarea>
  <p class="govuk-hint govuk-!-font-size-16 govuk-!-margin-bottom-0">
    One fact per line. Edit, delete or add lines as you need.
  </p>
</div>

<style>
  .agent-facts__examples {
    display: flex;
    gap: 10px;
    align-items: stretch;
    margin-bottom: 10px;
  }

  .agent-facts__example-select {
    flex: 1 1 auto;
    min-width: 0;
  }

  /* The "Load example" button stays on one line. */
  .agent-facts__examples :global(button) {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  /* The facts are set in a fixed-width typeface, one per line, in a softly rounded grey box. */
  .agent-facts__text {
    margin-bottom: 10px;
    padding: 20px 16px;
    border: 1px solid #b1b4b6;
    border-radius: 10px;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
    font-size: 14px;
    line-height: 1.7;
  }
</style>
