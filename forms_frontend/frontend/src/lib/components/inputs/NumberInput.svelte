<script lang="ts">
  interface Props {
    label: string;
    hint?: string | null;
    isOptional?: boolean;
    value: string;
    error?: string;
  }

  let { label, hint = null, isOptional = false, value = $bindable(""), error = "" }: Props = $props();
</script>

<fieldset class="govuk-fieldset">
  <legend class="govuk-fieldset__legend govuk-fieldset__legend--l">
    <h1 class="govuk-fieldset__heading">
      {label}
      {#if isOptional}
        <span class="govuk-caption-l">(optional)</span>
      {/if}
    </h1>
  </legend>

  {#if hint}
    <div id="number-hint" class="govuk-hint">{hint}</div>
  {/if}

  {#if error}
    <p id="number-error" class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <input
    class="govuk-input govuk-input--width-10"
    class:govuk-input--error={!!error}
    id="number-input"
    name="number"
    type="text"
    inputmode="numeric"
    bind:value
    aria-describedby={[hint ? 'number-hint' : '', error ? 'number-error' : ''].filter(Boolean).join(' ') || undefined}
  />
</fieldset>
