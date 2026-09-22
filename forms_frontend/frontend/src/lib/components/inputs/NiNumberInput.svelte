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

  <div id="ni-hint" class="govuk-hint">
    {hint || "It's on your National Insurance card, benefit letter, payslip or P60. For example, 'QQ 12 34 56 C'."}
  </div>

  {#if error}
    <p id="ni-error" class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <input
    class="govuk-input govuk-input--width-10"
    class:govuk-input--error={!!error}
    id="ni-input"
    name="ni-number"
    type="text"
    spellcheck="false"
    bind:value
    aria-describedby={['ni-hint', error ? 'ni-error' : ''].filter(Boolean).join(' ')}
  />
</fieldset>
