<script lang="ts">
  import type { FormMetadata } from "../api";

  interface Props {
    metadata: FormMetadata | null;
    transcript?: Array<{ message: string }>;
    result?: { status: string; outcome?: string } | null;
    onBack: () => void;
  }

  let { metadata, transcript = [], result = null, onBack }: Props = $props();
  const exitMessage = $derived(result?.outcome === "exit_page"
    ? [...transcript].reverse().find(entry => entry.message && !entry.message.startsWith("[ENGINE LOG]"))?.message
    : null);
</script>

<div class="govuk-panel govuk-panel--confirmation">
  <h1 class="govuk-panel__title">{exitMessage ? "Journey ended" : "Answers collected"}</h1>
  <div class="govuk-panel__body">
    This prototype does not submit answers to a department.
  </div>
</div>

{#if exitMessage}
  <div class="govuk-inset-text" style="white-space: pre-wrap;">{exitMessage}</div>
{:else if metadata?.what_happens_next_markdown}
  <h2 class="govuk-heading-m">Original form: what happens next</h2>
  <p class="govuk-body">{metadata.what_happens_next_markdown}</p>
{/if}

{#if metadata?.support_url}
  <p class="govuk-body">
    <a href={metadata.support_url} class="govuk-link">
      {metadata.support_url_text || "Get help"}
    </a>
  </p>
{/if}

<p class="govuk-body" style="margin-top: 30px;">
  <button
    class="govuk-button govuk-button--secondary"
    onclick={onBack}
  >
    Complete another form
  </button>
</p>
