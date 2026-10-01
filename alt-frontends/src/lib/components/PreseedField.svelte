<script lang="ts">
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

  function loadExample() {
    const example = examples.find((candidate) => candidate.id === selectedExampleId);
    if (!example) return;
    value = example.build(new Date());
    onexample?.(example);
  }
</script>

<div class="govuk-form-group">
  <label class="govuk-label govuk-label--s" for="preseed">Pre-seeded facts</label>
  <div id="preseed-hint" class="govuk-hint">
    Anything the agent should know before it starts: names, dates, answers to yes/no questions. It answers each
    question from these facts and the profile bundle, and asks you only when neither covers it.
  </div>

  {#if examples.length}
    <div class="preseed__examples">
      <select class="govuk-select" id="preseed-example" aria-label="Example facts" bind:value={selectedExampleId}>
        <option value="">Choose an example…</option>
        {#each examples as example (example.id)}
          <option value={example.id}>{example.title}</option>
        {/each}
      </select>
      <button
        class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
        type="button"
        disabled={!selectedExampleId}
        onclick={loadExample}
      >
        Load example
      </button>
    </div>
    {#if selectedExampleId}
      <p class="govuk-body-s ss-muted">
        {examples.find((example) => example.id === selectedExampleId)?.description} Loading it also sets the
        autonomy policy the example needs.
      </p>
    {/if}
  {/if}

  <textarea class="govuk-textarea preseed__text" id="preseed" rows="10" aria-describedby="preseed-hint" bind:value
  ></textarea>
</div>

<style>
  .preseed__examples {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }

  .preseed__examples .govuk-select {
    flex: 1 1 260px;
    min-width: 0;
  }

  .preseed__text {
    font-size: 16px;
  }
</style>
