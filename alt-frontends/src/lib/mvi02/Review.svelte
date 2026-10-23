<script lang="ts">
  import type { AnswerSource } from './answers';
  import ReviewList from './ReviewList.svelte';

  interface Props {
    items: Array<{ label: string; value: string; source: AnswerSource }>;
    closing: string[];
  }

  let { items, closing }: Props = $props();

  // The ring is full once the call has finished. Its number is how many questions were answered
  // and the steps under it say who answered them. Submitting is the last stage, so it isn't counted.
  const total = $derived(items.length);
  const byAgent = $derived(items.filter((item) => item.source === 'facts').length);
  const byYou = $derived(total - byAgent);
  const steps = $derived(
    [
      { label: `Agent ${byAgent}`, show: byAgent > 0 },
      { label: `You ${byYou}`, show: byYou > 0 }
    ].filter((step) => step.show)
  );

  // The ring is drawn as an arc on a circle of radius 56, so a full turn is its circumference.
  const circumference = 2 * Math.PI * 56;
</script>

<div class="mvi2-screen">
  <div class="mvi2-summary">
    <div class="mvi2-ring">
      <svg width="132" height="132" viewBox="0 0 132 132" aria-hidden="true" focusable="false">
        <circle cx="66" cy="66" r="56" fill="none" stroke="#E4E8F7" stroke-width="14" />
        <circle
          cx="66"
          cy="66"
          r="56"
          fill="none"
          stroke="#0F7A52"
          stroke-width="14"
          stroke-linecap="round"
          stroke-dasharray="{circumference} {circumference}"
          transform="rotate(-90 66 66)"
        />
      </svg>
      <strong>{total}</strong>
      <span>{total === 1 ? 'answer' : 'answers'}</span>
    </div>
    <h1>Almost done</h1>
    <p>Review your answers, then submit.</p>

    <ol class="mvi2-steps">
      {#each steps as step (step.label)}
        <li>
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" focusable="false">
            <circle cx="14" cy="14" r="13" fill="#0F7A52" />
            <path d="M8 14.4L12.3 18.5L20 10.5" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>{step.label}</span>
        </li>
      {/each}
      <li class="mvi2-steps__next">
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" focusable="false">
          <circle cx="14" cy="14" r="12" fill="none" stroke="#02064A" stroke-width="3" />
          <circle cx="14" cy="14" r="5" fill="#12E2F7" />
        </svg>
        <span>Submit</span>
      </li>
    </ol>
  </div>

  <ReviewList {items} scroll />

  {#each closing as message, index (index)}
    <p class="mvi2-closing">{message}</p>
  {/each}
</div>
