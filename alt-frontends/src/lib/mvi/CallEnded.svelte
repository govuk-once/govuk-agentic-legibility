<script lang="ts">
  interface Props {
    status: string;
    clock: string;
    messages: string[];
    answers: Array<{ question: string; answer: string }>;
  }

  let { status, clock, messages, answers }: Props = $props();

  const statusText = $derived(status === 'COMPLETED' ? 'Completed' : status.charAt(0) + status.slice(1).toLowerCase());
</script>

<div class="govuk-panel govuk-panel--confirmation">
  <h1 class="govuk-panel__title">Call ended</h1>
  <div class="govuk-panel__body">{statusText} · {clock}</div>
</div>

{#each messages as message, index (index)}
  <p class="govuk-body">{message}</p>
{/each}

{#if answers.length > 0}
  <details class="govuk-details" data-module="govuk-details">
    <summary class="govuk-details__summary">
      <span class="govuk-details__summary-text">Your answers</span>
    </summary>
    <div class="govuk-details__text">
      <dl class="govuk-summary-list govuk-!-margin-bottom-0">
        {#each answers as item, index (index)}
          <div class="govuk-summary-list__row">
            <dt class="govuk-summary-list__key">{item.question}</dt>
            <dd class="govuk-summary-list__value">{item.answer}</dd>
          </div>
        {/each}
      </dl>
    </div>
  </details>
{/if}

<style>
  /* GOV.UK puts a grey bar down the left of an opened details box. On the phone the answers sit
     straight under the heading with no bar. */
  .govuk-details__text {
    border-left: 0;
    padding-left: 0;
  }
</style>
