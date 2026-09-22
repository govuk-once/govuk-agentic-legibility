<script lang="ts">
  import type { FormMetadata } from "../api";

  interface Props {
    metadata: FormMetadata | null;
    onBack: () => void;
  }

  let { metadata, onBack }: Props = $props();
</script>

<div class="govuk-panel govuk-panel--confirmation">
  <h1 class="govuk-panel__title">Form submitted</h1>
  <div class="govuk-panel__body">
    Your answers have been submitted successfully
  </div>
</div>

{#if metadata?.what_happens_next_markdown}
  <h2 class="govuk-heading-m">What happens next</h2>
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
