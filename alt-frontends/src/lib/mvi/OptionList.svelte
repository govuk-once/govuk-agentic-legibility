<script lang="ts">
  // Shared (src/lib/schema/kind.ts): the option type
  import type { Choice } from '$lib/schema/kind';

  interface Props {
    choices: Choice[];
    /** Option numbers the user has keyed. */
    highlighted: number[];
    /** Option numbers suggested from the context panel. */
    suggested: number[];
  }

  let { choices, highlighted, suggested }: Props = $props();

  // A suggestion only shows until the user keys something.
  const showSuggestion = $derived(highlighted.length === 0);
</script>

<div role="list">
  {#each choices as choice, index (index)}
    {@const number = index + 1}
    {@const isSuggested = showSuggestion && suggested.includes(number)}
    <div
      role="listitem"
      class="ss-card"
      class:ss-card--selected={highlighted.includes(number) || isSuggested}
    >
      <strong class="govuk-body govuk-!-font-size-19 govuk-!-font-weight-bold govuk-!-margin-0">{number}</strong>
      <span class="govuk-body govuk-!-margin-0">{choice.label}</span>
      <!-- Every row keeps room for this mark, so a suggestion never moves the row's contents. -->
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        visibility={isSuggested ? 'visible' : 'hidden'}
        role="img"
        aria-label={isSuggested ? 'Suggested from what the service already knows' : undefined}
        aria-hidden={isSuggested ? undefined : 'true'}
        focusable="false"
      >
        <circle cx="12" cy="12" r="12" fill="#1D70B8" />
        <text
          x="12"
          y="17"
          text-anchor="middle"
          font-size="14"
          font-weight="700"
          font-family="GDS Transport, arial, sans-serif"
          fill="#FFFFFF">A</text
        >
      </svg>
    </div>
  {/each}
</div>

<style>
  /* Each row is: the number in a fixed slot, the label taking the remaining width, then the
     suggestion mark at the right edge. The fixed number slot keeps every label lined up. */
  strong {
    flex: 0 0 22px;
    color: #1d70b8;
  }

  span {
    flex: 1 1 auto;
  }

  svg {
    flex: 0 0 24px;
  }
</style>
