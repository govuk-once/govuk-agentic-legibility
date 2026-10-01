<script lang="ts">
  interface TranscriptLine {
    role: string;
    text: string;
  }

  let { lines }: { lines: TranscriptLine[] } = $props();
</script>

<div class="transcript govuk-!-margin-bottom-6">
  {#each lines as line, index (index)}
    <div class="ss-card transcript__line transcript__line--{line.role}">
      <p class="govuk-body govuk-!-margin-0">
        <span class="ss-muted govuk-!-font-weight-bold">{line.role === 'user' ? 'You' : 'Agent'}</span>
        <br />
        {line.text}
      </p>
    </div>
  {:else}
    <p class="govuk-body ss-muted">No messages yet — say something to get started.</p>
  {/each}
</div>

<style>
  .transcript__line--user {
    padding-left: 1em;
    background-color: #f3f2f1;
  }
</style>
