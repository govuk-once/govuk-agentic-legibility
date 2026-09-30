<script lang="ts">
  import type { FormMetadata, AutoAnswered } from "../api";
  import AutoProgressLog from "./AutoProgressLog.svelte";
  import { marked } from "marked";

  interface Props {
    metadata: FormMetadata | null;
    transcript?: Array<{ message: string }>;
    result?: { status: string; outcome?: string } | null;
    autoAnswered?: AutoAnswered[];
    onBack: () => void;
  }

  let { metadata, transcript = [], result = null, autoAnswered = [], onBack }: Props = $props();
  

  const mockPaymentCompleted = $derived(result?.outcome === "mock_payment_completed");
  const mockPaymentCancelled = $derived(result?.outcome === "mock_payment_cancelled");

  const rawExitMessage = $derived(result?.outcome === "exit_page"
    ? [...transcript].reverse().find(entry => entry.message && !entry.message.startsWith("[ENGINE LOG]"))?.message
    : null);

  const exitMessageHtml = $derived(rawExitMessage 
    ? marked.parse(rawExitMessage) 
    : null);

  const whatHappensNextHtml = $derived(
    metadata?.what_happens_next_markdown 
      ? marked.parse(metadata.what_happens_next_markdown) 
      : ""
  );
</script>

<div class="govuk-panel" class:govuk-panel--confirmation={!mockPaymentCancelled}>
  <h1 class="govuk-panel__title">
    {mockPaymentCompleted ? "Simulated payment completed"
      : mockPaymentCancelled ? "Simulated payment cancelled"
      : rawExitMessage ? "Journey ended" : "Answers collected"}
  </h1>
  <div class="govuk-panel__body">
    {#if mockPaymentCompleted}
      No real payment was taken. Your application has not been submitted.
    {:else if mockPaymentCancelled}
      No payment was taken. Your application has not been submitted.
    {:else}
      This prototype does not submit answers to a department.
    {/if}
  </div>
</div>

{#if autoAnswered.length > 0}
  <AutoProgressLog items={autoAnswered} />
{/if}

{#if rawExitMessage}
  <div class="govuk-inset-text" style="white-space: pre-wrap;">{@html exitMessageHtml}</div>
{:else if !mockPaymentCompleted && !mockPaymentCancelled && metadata?.what_happens_next_markdown}
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