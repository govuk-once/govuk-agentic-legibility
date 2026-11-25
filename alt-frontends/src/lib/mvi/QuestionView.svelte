<script lang="ts">
  // Shared (src/lib/schema/kind.ts): the option type
  import type { Choice } from '$lib/schema/kind';
  import OptionList from './OptionList.svelte';

  interface Props {
    prompt: string;
    choices: Choice[] | null;
    highlighted: number[];
    suggested: number[];
    error: string | null;
  }

  let { prompt, choices, highlighted, suggested, error }: Props = $props();

  // A prompt can run over several lines: the first is the question, the rest read as detail.
  const lines = $derived(prompt.split('\n').filter((line) => line.trim() !== ''));
</script>

<div class="govuk-!-text-align-centre">
  <h1 class="govuk-heading-l govuk-!-margin-bottom-6">{lines[0] ?? ''}</h1>
  {#each lines.slice(1) as line, index (index)}
    <p class="govuk-body-s">{line}</p>
  {/each}
</div>

{#if choices}
  <OptionList {choices} {highlighted} {suggested} />
{/if}

{#if error}
  <p class="govuk-error-message">{error}</p>
{/if}
