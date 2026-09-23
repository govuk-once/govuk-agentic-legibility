<script lang="ts">
  import type { FormMetadata, AutoAnswered } from "../api";
  import AutoProgressLog from "./AutoProgressLog.svelte";
  import { marked } from "marked"; // 1. Import marked

  interface Props {
    metadata: FormMetadata | null;
    transcript?: Array<{ message: string }>;
    result?: { status: string; outcome?: string } | null;
    autoAnswered?: AutoAnswered[];
    onBack: () => void;
  }

  let { metadata, transcript = [], result = null, autoAnswered = [], onBack }: Props = $props();
  
  const exitMessage = $derived(result?.outcome === "exit_page"
    ? [...transcript].reverse().find(entry => entry.message && !entry.message.startsWith("[ENGINE LOG]"))?.message
    : null);

  // 2. Derive the parsed HTML string
  const whatHappensNextHtml = $derived(
    metadata?.what_happens_next_markdown 
      ? marked.parse(metadata.what_happens_next_markdown) 
      : ""
  );
</script>

<div class="govuk-panel govuk-panel--confirmation">
  <h1 class="govuk-panel__title">{exitMessage ? "Journey ended" : "Answers collected"}</h1>
  <div class="govuk-panel__body">
    This prototype does not submit answers to a department.
  </div>
</div>

{#if autoAnswered.length > 0}
  <AutoProgressLog items={autoAnswered} />
{/if}

{#if exitMessage}
  <div class="govuk-inset-text" style="white-space: pre-wrap;">{exitMessage}</div>
{:else if metadata?.what_happens_next_markdown}
  <h2 class="govuk-heading-m">What happens next</h2>
  <!-- 3. Render using {@html}. Use a <div> instead of <p> because marked outputs <p> tags by default -->
  <div class="govuk-body">
    {@html whatHappensNextHtml}
  </div>
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