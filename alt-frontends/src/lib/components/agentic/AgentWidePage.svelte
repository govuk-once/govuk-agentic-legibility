<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="agent-wide-page">
  {@render children()}
</div>

<style>
  /* The page is wider than the 960px GOV.UK container it sits in, centred on the same line, and
     shrinks to fit narrow windows. The design is laid out for a wide screen. */
  .agent-wide-page {
    width: min(1360px, 100vw - 80px);
    margin-left: calc(50% - min(680px, 50vw - 40px));
  }

  /* Text boxes and buttons have softly rounded corners, and buttons have no line under them, as on
     the other redesigned pages. */
  .agent-wide-page :global(.govuk-input),
  .agent-wide-page :global(.govuk-select),
  .agent-wide-page :global(.govuk-textarea) {
    border-radius: 8px;
  }

  .agent-wide-page :global(.govuk-button) {
    border-radius: 8px;
    box-shadow: none;
  }

  /* gov.css gives a focused button a black line under it. That is removed too; the yellow fill
     stays as the sign of focus. */
  .agent-wide-page :global(.govuk-button:focus:not(:active):not(:hover)) {
    box-shadow: none;
  }
</style>
