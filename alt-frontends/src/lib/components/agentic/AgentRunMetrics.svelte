<script lang="ts">
  interface Props {
    /** The figures along the top, each a label over a value, for example "Events logged" over "11". */
    figures: { label: string; value: string }[];
    /** The bar's parts, as shares that add up to 100. Left out until there is something to show. */
    split?: { label: string; share: number; colour: 'engine' | 'agent' | 'you' }[];
  }

  let { figures, split = [] }: Props = $props();
</script>

<section class="agent-metrics" aria-labelledby="agent-metrics-title">
  <h2 id="agent-metrics-title" class="govuk-heading-s govuk-!-margin-bottom-3">Metrics</h2>

  <div class="agent-metrics__body">
  <dl class="agent-metrics__figures">
    {#each figures as figure (figure.label)}
      <div>
        <dt class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0">{figure.label}</dt>
        <dd class="govuk-heading-m govuk-!-margin-0">{figure.value}</dd>
      </div>
    {/each}
  </dl>

  {#if split.length > 0}
    <div class="agent-metrics__split" role="img" aria-label={split.map((part) => `${part.label} ${part.share}%`).join(', ')}>
      {#each split as part (part.label)}
        <span
          class="agent-metrics__segment agent-metrics__segment--{part.colour}"
          style:flex-grow={Math.max(part.share, 1)}
        ></span>
      {/each}
    </div>
    <div class="agent-metrics__legend">
      {#each split as part (part.label)}
        <span class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0" style:flex-grow={Math.max(part.share, 1)}>
          {part.label} {part.share}%
        </span>
      {/each}
    </div>
  {/if}
  </div>
</section>

<style>
  .agent-metrics {
    padding: 20px;
  }

  /* The figures, the bar and its labels share one box that is as wide as the figures. That makes the
     bar run exactly from the left edge of the first figure to the right edge of the last. */
  .agent-metrics__body {
    width: fit-content;
    max-width: 100%;
  }

  .agent-metrics__figures {
    display: flex;
    flex-wrap: wrap;
    gap: 16px 48px;
    margin: 0 0 16px;
  }

  /* One thin rounded bar split into coloured parts, each as long as its share of the time. */
  .agent-metrics__split {
    display: flex;
    gap: 4px;
    height: 8px;
  }

  .agent-metrics__legend {
    display: flex;
    gap: 4px;
    margin-top: 8px;
  }

  .agent-metrics__legend > span {
    flex-basis: 0;
    min-width: max-content;
  }

  .agent-metrics__segment {
    flex-basis: 0;
    border-radius: 4px;
  }

  .agent-metrics__segment--engine {
    background-color: #1d70b8;
  }

  .agent-metrics__segment--agent {
    background-color: #a5c8e8;
  }

  .agent-metrics__segment--you {
    background-color: #ffdd00;
  }
</style>
