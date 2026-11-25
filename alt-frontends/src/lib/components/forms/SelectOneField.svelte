<script lang="ts">
  import type { Choice } from '$lib/schema/kind';

  interface Props {
    choices: Choice[];
    value: string;
  }

  let { choices, value = $bindable('') }: Props = $props();
</script>

<div class="govuk-radios" data-module="govuk-radios">
  {#each choices as choice, index (choice.value)}
    <div class="govuk-radios__item">
      <input
        class="govuk-radios__input"
        id={`select-one-field-${index}`}
        type="radio"
        checked={value === choice.value}
        onclick={() => (value = choice.value)}
      />
      <label class="govuk-label govuk-radios__label" for={`select-one-field-${index}`}>
        {choice.label}
      </label>
    </div>
  {/each}
</div>
