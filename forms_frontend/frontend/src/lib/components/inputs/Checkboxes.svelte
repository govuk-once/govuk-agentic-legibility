<script lang="ts">
  interface CheckboxOption {
    value: string;
    label: string;
  }

  interface Props {
    name?: string;
    label: string;
    hint?: string | null;
    isOptional?: boolean;
    options: CheckboxOption[];
    value: string[];
    error?: string;
  }

  let {
    name = "checkboxes",
    label,
    hint = null,
    isOptional = false,
    options,
    value = $bindable([]),
    error = "",
  }: Props = $props();

  function toggle(optionValue: string, checked: boolean) {
    const selected = Array.isArray(value) ? value : [];
    // Create a fresh array: accepted answers and proposal values may be reused
    // elsewhere in the session, and checkbox interaction must not mutate them.
    value = checked
      ? (selected.includes(optionValue) ? selected : [...selected, optionValue])
      : selected.filter((item) => item !== optionValue);
  }
</script>

<fieldset class="govuk-fieldset" aria-describedby={[hint ? `${name}-hint` : '', error ? `${name}-error` : ''].filter(Boolean).join(' ') || undefined}>
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

  <div class="govuk-checkboxes" data-module="govuk-checkboxes">
    {#each options as opt, i}
      <div class="govuk-checkboxes__item">
        <input
          class="govuk-checkboxes__input"
          id="{name}-{i}"
          {name}
          type="checkbox"
          value={opt.value}
          checked={Array.isArray(value) && value.includes(opt.value)}
          onchange={(event) => toggle(opt.value, event.currentTarget.checked)}
        />
        <label class="govuk-label govuk-checkboxes__label" for="{name}-{i}">
          {opt.label}
        </label>
      </div>
    {/each}
  </div>
</fieldset>
