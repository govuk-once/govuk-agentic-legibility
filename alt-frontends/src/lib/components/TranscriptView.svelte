<script lang="ts">
  interface TranscriptLine {
    role: string;
    text: string;
  }

  let { lines }: { lines: TranscriptLine[] } = $props();
</script>

<div class="transcript govuk-!-margin-bottom-6">
  {#each lines as line, index (index)}
    {#if line.role === 'user'}
      <div class="transcript__user">
        <p class="govuk-body govuk-!-margin-0">{line.text}</p>
      </div>
    {:else}
      <div class="transcript__agent">
        <span class="govuk-body govuk-!-font-size-16 govuk-!-font-weight-bold govuk-!-margin-0 ss-muted">Agent</span>
        <p class="govuk-body govuk-!-margin-0">{line.text}</p>
      </div>
    {/if}
  {:else}
    <p class="govuk-body ss-muted">No messages yet — say something to get started.</p>
  {/each}
</div>

<style>
  .transcript {
    display: flex;
    flex-direction: column;
    gap: 26px;
  }

  /* What you said: a grey bubble on the right, with the bottom right corner squared off. */
  .transcript__user {
    align-self: flex-end;
    max-width: 520px;
    padding: 14px 18px;
    border-radius: 16px 16px 4px 16px;
    background-color: #f3f2f1;
  }

  .transcript__agent {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 0 4px;
  }
</style>
