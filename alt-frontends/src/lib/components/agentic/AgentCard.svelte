<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    /** The card's heading, for example "Facts for this run". */
    title: string;
    /** A short note in the header's right-hand corner, for example the journey name. */
    note?: string;
    /** Something in the header's right-hand corner instead of a note, for example a drop-down. */
    aside?: Snippet;
    children: Snippet;
  }

  let { title, note, aside, children }: Props = $props();
</script>

<section class="agent-card">
  <header class="agent-card__header">
    <h2 class="govuk-heading-s govuk-!-margin-0">{title}</h2>
    {#if aside}
      {@render aside()}
    {:else if note}
      <span class="agent-card__note govuk-!-font-size-14">{note}</span>
    {/if}
  </header>
  <div class="agent-card__body">
    {@render children()}
  </div>
</section>

<style>
  /* A white card with a thin grey outline, rounded corners, and a header split from the body by
     a line. */
  .agent-card {
    overflow: hidden;
    border: 1px solid #b1b4b6;
    border-radius: 14px;
    background-color: #ffffff;
  }

  .agent-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 24px;
    border-bottom: 1px solid #b1b4b6;
  }

  /* The note is set in a fixed-width typeface, as in the design. */
  .agent-card__note {
    color: #505a5f;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
  }

  .agent-card__body {
    padding: 24px;
  }
</style>
