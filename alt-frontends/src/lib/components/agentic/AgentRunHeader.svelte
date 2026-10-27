<script lang="ts">
  interface Props {
    /** The run's id, shown large in a fixed-width typeface. */
    runId: string;
    /** What the run is doing, for example "Waiting for you". */
    statusLabel: string;
    /** Which GOV.UK tag colour to use for the status. */
    statusColour: 'blue' | 'green' | 'grey' | 'yellow';
    /** The parts of the line under the id, for example "DVLA: Change of address", "Assertive", "4 steps done". */
    summary: string[];
    /** Whether the Stop agent button can be pressed. */
    canStop: boolean;
    onstop: () => void;
  }

  let { runId, statusLabel, statusColour, summary, canStop, onstop }: Props = $props();
</script>

<header class="agent-run-header">
  <div>
    <div class="agent-run-header__title">
      <h1 class="govuk-heading-m govuk-!-margin-0 agent-run-header__id">{runId}</h1>
      <strong class="govuk-tag govuk-tag--{statusColour}">{statusLabel}</strong>
    </div>
    <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-top-2 govuk-!-margin-bottom-0 agent-run-header__summary">
      {#each summary as part (part)}
        <span>{part}</span>
      {/each}
    </p>
  </div>

  <button
    class="govuk-button govuk-button--warning govuk-!-margin-bottom-0"
    type="button"
    disabled={!canStop}
    onclick={onstop}
  >
    Stop agent
  </button>
</header>

<style>
  .agent-run-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 30px;
  }

  .agent-run-header__title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 14px;
  }

  /* The id and the line under it are set in a fixed-width typeface, as in the design. */
  .agent-run-header__id,
  .agent-run-header__summary {
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
  }

  .agent-run-header__id {
    overflow-wrap: anywhere;
  }

  /* The parts of the summary sit side by side with a gap between them. */
  .agent-run-header__summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0 16px;
  }
</style>
