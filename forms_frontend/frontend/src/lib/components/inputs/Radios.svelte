<script lang="ts">
  interface RadioOption {
    value: string;
    label: string;
  }

  interface Props {
    name?: string;
    label: string;
    hint?: string | null;
    isOptional?: boolean;
    options: RadioOption[];
    value: string | null;
    error?: string;
  }

  let { name = "radios", label, hint = null, isOptional = false, options, value = $bindable(null), error = "" }: Props = $props();

  function handleChange(optValue: string) {
    value = optValue;
  }
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

  <div class="govuk-radios" data-module="govuk-radios">
    {#each options as opt, i}
      <div class="govuk-radios__item">
        <input
          class="govuk-radios__input"
          id="{name}-{i}"
          {name}
          type="radio"
          value={opt.value}
          checked={value === opt.value}
          onchange={() => handleChange(opt.value)}
        />
        <label class="govuk-label govuk-radios__label" for="{name}-{i}">
          {opt.label}
        </label>
      </div>
    {/each}
  </div>
</fieldset>
