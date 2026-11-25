<script lang="ts">
  interface Props {
    /** What has been keyed so far, as shown large. */
    readout: string;
    /** Small line under the readout. */
    caption: string;
    error: string | null;
  }

  let { readout, caption, error }: Props = $props();

  // Long answers such as an address step down in size so they still fit.
  const sizeClass = $derived(
    readout.length <= 8
      ? 'govuk-!-font-size-80'
      : readout.length <= 14
        ? 'govuk-!-font-size-48'
        : readout.length <= 28
          ? 'govuk-!-font-size-27'
          : 'govuk-!-font-size-19'
  );
</script>

<div class="govuk-!-text-align-centre govuk-!-padding-top-6 govuk-!-padding-bottom-6">
  <p class="govuk-body {sizeClass} govuk-!-font-weight-bold govuk-!-text-break-word govuk-!-margin-0" aria-live="polite">
    {readout}
  </p>
  <p class="govuk-body-s ss-muted govuk-!-margin-top-6 govuk-!-margin-bottom-0">{caption}</p>
</div>

{#if error}
  <p class="govuk-error-message">{error}</p>
{/if}
