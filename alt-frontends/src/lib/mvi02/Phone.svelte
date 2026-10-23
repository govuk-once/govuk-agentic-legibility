<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';

  interface Props {
    /** The status pill in the header. Left out on the start screens. */
    pill?: { label: string; time?: string; state: 'live' | 'off' };
    children: Snippet;
    /** The keypad under the card. */
    footer?: Snippet;
    /** Something laid over the whole phone, such as the facts panel. */
    overlay?: Snippet;
  }

  let { pill, children, footer, overlay }: Props = $props();
</script>

<div class="mvi2-device">
<section class="mvi2-phone" aria-label="Phone">
  <header class="mvi2-header">
    <div class="mvi2-logo">
      <span class="mvi2-logo__mark"><Icon name="logo" /></span>
      <span class="mvi2-logo__text">GOV.UK</span>
    </div>
    {#if pill}
      <div class="mvi2-pill">
        <span class="mvi2-pill__dot" class:mvi2-pill__dot--off={pill.state === 'off'}></span>
        <strong>{pill.label}</strong>
        {#if pill.time}
          <span class="mvi2-pill__time">{pill.time}</span>
        {/if}
      </div>
    {/if}
  </header>

  {@render children()}

  {#if footer}
    {@render footer()}
  {/if}

  {#if overlay}
    {@render overlay()}
  {/if}
</section>
</div>
