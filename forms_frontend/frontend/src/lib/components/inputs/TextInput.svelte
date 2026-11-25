<script lang="ts">
  interface Props {
    name?: string;
    label: string;
    hint?: string | null;
    isOptional?: boolean;
    value: string;
    error?: string;
  }

  let { name = "text-input", label, hint = null, isOptional = false, value = $bindable(""), error = "" }: Props = $props();
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
    <div id="{name}-hint" class="govuk-hint">{hint}</div>
  {/if}

  {#if error}
    <p id="{name}-error" class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <input
    class="govuk-input"
    class:govuk-input--error={!!error}
    id={name}
    {name}
    type="text"
    bind:value
    aria-describedby={[hint ? `${name}-hint` : '', error ? `${name}-error` : ''].filter(Boolean).join(' ') || undefined}
  />
</fieldset>
