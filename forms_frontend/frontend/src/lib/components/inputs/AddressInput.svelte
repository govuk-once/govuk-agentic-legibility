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

  let line1 = $state("");
  let line2 = $state("");
  let town = $state("");
  let county = $state("");
  let postcode = $state("");

  $effect(() => {
    const parts = [line1, line2, town, county, postcode]
      .map((p) => p.trim())
      .filter(Boolean);
    value = parts.join(", ");
  });
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
    <div class="govuk-hint">{hint}</div>
  {/if}

  {#if error}
    <p class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  <div class="govuk-form-group">
    <label class="govuk-label" for="address-line-1">Address line 1</label>
    <input
      class="govuk-input"
      class:govuk-input--error={!!error}
      id="address-line-1"
      name="address-line-1"
      type="text"
      autocomplete="address-line1"
      bind:value={line1}
    />
  </div>

  <div class="govuk-form-group">
    <label class="govuk-label" for="address-line-2">Address line 2 (optional)</label>
    <input
      class="govuk-input"
      id="address-line-2"
      name="address-line-2"
      type="text"
      autocomplete="address-line2"
      bind:value={line2}
    />
  </div>

  <div class="govuk-form-group">
    <label class="govuk-label" for="address-town">Town or city</label>
    <input
      class="govuk-input govuk-!-width-two-thirds"
      id="address-town"
      name="address-town"
      type="text"
      autocomplete="address-level2"
      bind:value={town}
    />
  </div>

  <div class="govuk-form-group">
    <label class="govuk-label" for="address-county">County (optional)</label>
    <input
      class="govuk-input govuk-!-width-two-thirds"
      id="address-county"
      name="address-county"
      type="text"
      bind:value={county}
    />
  </div>

  <div class="govuk-form-group">
    <label class="govuk-label" for="address-postcode">Postcode</label>
    <input
      class="govuk-input govuk-input--width-10"
      id="address-postcode"
      name="address-postcode"
      type="text"
      autocomplete="postal-code"
      bind:value={postcode}
    />
  </div>
</fieldset>
