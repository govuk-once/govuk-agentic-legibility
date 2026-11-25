<script lang="ts">
  import AgentCard from './AgentCard.svelte';

  interface Props {
    /** The choices made so far, shown as label and value rows, for example "Autonomy" and "Assertive". */
    details: { label: string; value: string }[];
    /** Whether the agent starts answering as soon as the run starts. */
    runImmediately: boolean;
    starting: boolean;
    canStart: boolean;
    onstart: () => void;
  }

  let { details, runImmediately = $bindable(), starting, canStart, onstart }: Props = $props();
</script>

<AgentCard title="Run summary">
  <dl class="agent-summary__details">
    {#each details as detail (detail.label)}
      <div class="agent-summary__row">
        <dt class="govuk-body govuk-!-margin-0 ss-muted">{detail.label}</dt>
        <dd class="govuk-body govuk-!-margin-0 agent-summary__value">{detail.value}</dd>
      </div>
    {/each}
  </dl>

  <div class="agent-summary__start">
    <div class="govuk-checkboxes govuk-checkboxes--small">
      <div class="govuk-checkboxes__item">
        <input class="govuk-checkboxes__input" id="run-immediately" type="checkbox" bind:checked={runImmediately} />
        <label class="govuk-label govuk-checkboxes__label" for="run-immediately">
          Start answering straight away
        </label>
      </div>
    </div>

    <button
      class="govuk-button govuk-!-margin-bottom-0 agent-summary__button"
      type="button"
      disabled={starting || !canStart}
      onclick={onstart}
    >
      {starting ? 'Starting…' : 'Start autonomous run'}
    </button>
  </div>
</AgentCard>

<style>
  .agent-summary__details {
    margin: 0;
  }

  .agent-summary__row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 11px 0;
    border-bottom: 1px solid #ecece8;
  }

  .agent-summary__row:first-child {
    padding-top: 0;
  }

  .agent-summary__value {
    text-align: right;
  }

  /* The checkbox and the button sit under the details, split from them by a line. */
  .agent-summary__start {
    margin-top: 18px;
  }

  .agent-summary__button {
    width: 100%;
    margin-top: 14px;
  }
</style>
