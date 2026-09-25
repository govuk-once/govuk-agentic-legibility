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
    <div id="email-hint" class="govuk-hint">{hint}</div>
  {/if}

  {#if error}
    <p id="email-error" class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <input
    class="govuk-input"
    class:govuk-input--error={!!error}
    id="email-input"
    name="email"
    type="email"
    spellcheck="false"
    autocomplete="email"
    bind:value
    aria-describedby={[hint ? 'email-hint' : '', error ? 'email-error' : ''].filter(Boolean).join(' ') || undefined}
  />
</fieldset>
