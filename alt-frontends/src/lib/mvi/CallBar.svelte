<script lang="ts">
  interface Props {
    department?: string;
    clock?: string;
  }

  let { department = '', clock = '' }: Props = $props();
</script>

<div class="govuk-header">
  <div class="govuk-grid-row govuk-!-padding-left-4 govuk-!-padding-right-4 govuk-!-padding-top-2 govuk-!-padding-bottom-2">
    <div class="govuk-grid-column-one-half">
      <strong>GOV.UK</strong>
    </div>
    {#if department || clock}
      <div class="govuk-grid-column-one-half govuk-!-text-align-right">
        {department ? `${department} · ` : ''}{clock}
      </div>
    {/if}
  </div>
</div>

<style>
  /* GOV.UK's header carries a thick white line under it. Inside the phone that just reads as a
     gap between the black bar and the screen below, so it is taken off. */
  .govuk-header {
    border-bottom: 0;
  }
</style>
