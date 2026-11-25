<script lang="ts">
  import type { AnswerSource } from './answers';

  interface Props {
    items: Array<{ label: string; value: string; source: AnswerSource }>;
    /** Sits on the card's own background instead of a white one, for use inside a white card. */
    inset?: boolean;
    /** Scrolls to the newest row as rows are added. */
    follow?: boolean;
    /** Scrolls inside its own box instead of growing. */
    scroll?: boolean;
  }

  let { items, inset = false, follow = false, scroll = false }: Props = $props();

  const tags: Record<AnswerSource, string> = {
    facts: 'From your facts',
    said: 'You said it',
    confirmed: 'You confirmed'
  };

  // Keeps the newest row in view when the list grows.
  function showLast(node: HTMLElement) {
    if (follow && items.length > 0) node.lastElementChild?.scrollIntoView({ block: 'nearest' });
  }
</script>

<div class="mvi2-review" class:mvi2-review--inset={inset} class:mvi2-review--scroll={scroll} {@attach showLast}>
  {#each items as item, index (index)}
    <div class="mvi2-review__row">
      <span class="mvi2-review__label">{item.label}</span>
      <span class="mvi2-review__value">{item.value}</span>
      <span class="mvi2-badge" class:mvi2-badge--facts={item.source === 'facts'}>{tags[item.source]}</span>
    </div>
  {:else}
    <div class="mvi2-review__row">
      <span class="mvi2-review__label">Nothing was asked.</span>
    </div>
  {/each}
</div>
