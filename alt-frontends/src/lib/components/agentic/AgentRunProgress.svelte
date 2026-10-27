<script lang="ts">
  interface Props {
    /** A sentence on where the run stands. */
    summary: string;
    /** How many questions have been answered in all. */
    done: number;
    /** How many of those you answered yourself. */
    answeredByYou: number;
    /** Whether a question is waiting for you. */
    needsYou: boolean;
    /** Set when the agent is paused and can be started again. */
    onresume?: () => void;
    /** A problem to show, for example that the agent could not carry on. */
    error?: string | null;
  }

  let { summary, done, answeredByYou, needsYou, onresume, error = null }: Props = $props();

  // The three figures under the sentence.
  const figures = $derived([
    { label: 'Done', value: done, highlight: false },
    { label: 'Answered by you', value: answeredByYou, highlight: false },
    { label: 'Needs you', value: needsYou ? 1 : 0, highlight: needsYou }
  ]);
</script>

<section class="agent-progress" aria-labelledby="agent-progress-title">
  <h2 id="agent-progress-title" class="govuk-heading-s govuk-!-margin-bottom-2">Where the run stands</h2>
  <p class="govuk-body govuk-!-margin-bottom-3">{summary}</p>

  {#if error}
    <p class="govuk-error-message">{error}</p>
  {/if}

  <div class="agent-progress__figures">
    {#each figures as figure (figure.label)}
      <div class="agent-progress__figure" class:agent-progress__figure--highlight={figure.highlight}>
        <span class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0">{figure.label}</span>
        <span class="govuk-heading-m govuk-!-margin-0">{figure.value}</span>
      </div>
    {/each}
  </div>

  {#if onresume}
    <button class="govuk-button ss-cta govuk-!-margin-top-4 govuk-!-margin-bottom-0" type="button" onclick={onresume}>
      Resume agent
    </button>
  {/if}
</section>

<style>
  .agent-progress__figures {
    display: flex;
    gap: 10px;
  }

  .agent-progress__figure {
    display: flex;
    flex: 1 1 0;
    flex-direction: column;
    gap: 2px;
    padding: 10px 14px;
    border: 1px solid #b1b4b6;
    border-radius: 8px;
  }

  /* The figure for a question waiting for you has a yellow outline. */
  .agent-progress__figure--highlight {
    border: 2px solid #ffdd00;
  }
</style>
