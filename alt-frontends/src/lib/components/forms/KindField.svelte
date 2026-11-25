<script lang="ts">
  import type { AwaitingInput, PrefillSuggestion } from '$lib/types';
  import { coerceSubmission, resolveChoices, resolveFieldKind } from '$lib/schema/kind';
  import BooleanField from './BooleanField.svelte';
  import StringField from './StringField.svelte';
  import SelectOneField from './SelectOneField.svelte';
  import SelectManyField from './SelectManyField.svelte';
  import FileRefField from './FileRefField.svelte';

  interface Props {
    awaiting: AwaitingInput;
    onsubmit: (value: unknown) => void;
    suggestion?: PrefillSuggestion | null;
  }

  let { awaiting, onsubmit, suggestion = null }: Props = $props();

  const fieldKind = $derived(resolveFieldKind(awaiting.schema));
  const choices = $derived(resolveChoices(awaiting.schema));

  let rawValue: unknown = $state(null);
  let suggestionVisible = $state(false);

  function blankValue(): unknown {
    return fieldKind === 'select_many' ? [] : fieldKind === 'boolean' ? null : '';
  }

  $effect(() => {
    // Reset to a kind-appropriate default whenever a new field is awaited —
    // or, if an LLM suggestion was found for this field, seed the field with
    // it instead. Either way the field stays fully editable and nothing is
    // ever auto-submitted.
    awaiting.token;
    if (suggestion && suggestion.value !== null && suggestion.value !== undefined) {
      rawValue = suggestion.value;
      suggestionVisible = true;
    } else {
      rawValue = blankValue();
      suggestionVisible = false;
    }
  });

  function clearSuggestion() {
    rawValue = blankValue();
    suggestionVisible = false;
  }

  function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    onsubmit(coerceSubmission(fieldKind, rawValue));
  }
</script>

<form class="govuk-form-group" onsubmit={handleSubmit}>
  <fieldset class="govuk-fieldset">
    <legend class="govuk-fieldset__legend govuk-fieldset__legend--m">
      {awaiting.prompt}
    </legend>

    {#if suggestionVisible && suggestion}
      <div class="govuk-inset-text govuk-!-margin-top-0">
        Suggested from your notes: {suggestion.reason}. Check this is correct before continuing.
        <br />
        <button
          type="button"
          class="govuk-button govuk-button--secondary govuk-button--small govuk-!-margin-top-2 govuk-!-margin-bottom-0"
          onclick={clearSuggestion}
        >
          Clear suggestion
        </button>
      </div>
    {/if}

    {#if fieldKind === 'boolean'}
      <BooleanField bind:value={rawValue as boolean | null} />
    {:else if fieldKind === 'select_one'}
      <SelectOneField {choices} bind:value={rawValue as string} />
    {:else if fieldKind === 'select_many'}
      <SelectManyField {choices} bind:value={rawValue as string[]} />
    {:else if fieldKind === 'file_ref'}
      <FileRefField schema={awaiting.schema} bind:value={rawValue as { ref: string; bytes: number } | null} />
    {:else}
      <StringField schema={awaiting.schema} bind:value={rawValue as string} />
    {/if}
  </fieldset>

  <button class="govuk-button" type="submit" data-module="govuk-button">Continue</button>
</form>
