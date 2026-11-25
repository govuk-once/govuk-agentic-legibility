<script lang="ts">
  import type { Choice } from '$lib/schema/kind';

  interface Props {
    choices: Choice[];
    value: string[];
  }

  let { choices, value = $bindable([]) }: Props = $props();

  function toggle(choiceValue: string, checked: boolean) {
    value = checked ? [...value, choiceValue] : value.filter((v) => v !== choiceValue);
  }
</script>

<div class="govuk-checkboxes" data-module="govuk-checkboxes">
  {#each choices as choice, index (choice.value)}
    <div class="govuk-checkboxes__item">
      <input
        class="govuk-checkboxes__input"
        id={`select-many-field-${index}`}
        type="checkbox"
        checked={value.includes(choice.value)}
        onchange={(event) => toggle(choice.value, (event.target as HTMLInputElement).checked)}
      />
      <label class="govuk-label govuk-checkboxes__label" for={`select-many-field-${index}`}>
        {choice.label}
      </label>
    </div>
  {/each}
</div>
