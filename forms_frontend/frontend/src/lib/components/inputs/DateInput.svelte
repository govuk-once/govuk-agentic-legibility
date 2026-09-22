<script lang="ts">
  interface Props {
    label: string;
    hint?: string | null;
    settings?: Record<string, any>;
    isOptional?: boolean;
    value: string;
    error?: string;
  }

  let { label, hint = null, settings = {}, isOptional = false, value = $bindable(""), error = "" }: Props = $props();

  let day = $state("");
  let month = $state("");
  let year = $state("");

  const isDateOfBirth = $derived(settings?.input_type === "date_of_birth");
  const defaultHint = $derived(
    isDateOfBirth ? "For example, 27 3 1998" : "For example, 27 3 2024"
  );

  $effect(() => {
    if (day && month && year) {
      value = `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year}`;
    } else {
      value = "";
    }
  });
</script>

<fieldset class="govuk-fieldset" role="group" aria-describedby="date-hint">
  <legend class="govuk-fieldset__legend govuk-fieldset__legend--l">
    <h1 class="govuk-fieldset__heading">
      {label}
      {#if isOptional}
        <span class="govuk-caption-l">(optional)</span>
      {/if}
    </h1>
  </legend>

  <div id="date-hint" class="govuk-hint">
    {hint || defaultHint}
  </div>

  {#if error}
    <p id="date-error" class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <div class="govuk-date-input" id="date-input">
    <div class="govuk-date-input__item">
      <div class="govuk-form-group">
        <label class="govuk-label govuk-date-input__label" for="date-day">Day</label>
        <input
          class="govuk-input govuk-date-input__input govuk-input--width-2"
          class:govuk-input--error={!!error}
          id="date-day"
          name="date-day"
          type="text"
          inputmode="numeric"
          bind:value={day}
        />
      </div>
    </div>
    <div class="govuk-date-input__item">
      <div class="govuk-form-group">
        <label class="govuk-label govuk-date-input__label" for="date-month">Month</label>
        <input
          class="govuk-input govuk-date-input__input govuk-input--width-2"
          class:govuk-input--error={!!error}
          id="date-month"
          name="date-month"
          type="text"
          inputmode="numeric"
          bind:value={month}
        />
      </div>
    </div>
    <div class="govuk-date-input__item">
      <div class="govuk-form-group">
        <label class="govuk-label govuk-date-input__label" for="date-year">Year</label>
        <input
          class="govuk-input govuk-date-input__input govuk-input--width-4"
          class:govuk-input--error={!!error}
          id="date-year"
          name="date-year"
          type="text"
          inputmode="numeric"
          bind:value={year}
        />
      </div>
    </div>
  </div>
</fieldset>
