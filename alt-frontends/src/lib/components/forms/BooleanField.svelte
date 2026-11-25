<script lang="ts">
  interface Props {
    value: boolean | null;
  }

  let { value = $bindable(null) }: Props = $props();
</script>

<div class="govuk-radios" data-module="govuk-radios">
  <div class="govuk-radios__item">
    <input
      class="govuk-radios__input"
      id="boolean-field-yes"
      type="radio"
      checked={value === true}
      onclick={() => (value = true)}
    />
    <label class="govuk-label govuk-radios__label" for="boolean-field-yes">Yes</label>
  </div>
  <div class="govuk-radios__item">
    <input
      class="govuk-radios__input"
      id="boolean-field-no"
      type="radio"
      checked={value === false}
      onclick={() => (value = false)}
    />
    <label class="govuk-label govuk-radios__label" for="boolean-field-no">No</label>
  </div>
</div>
