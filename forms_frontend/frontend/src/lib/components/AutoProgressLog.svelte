<script lang="ts">
  import type { AutoAnswered } from "../api";

  interface Props {
    items: AutoAnswered[];
  }

  let { items }: Props = $props();
  let expanded = $state(false);

  function formatValue(val: any): string {
    if (val === true) return "Yes";
    if (val === false) return "No";
    if (Array.isArray(val)) return val.join(", ");
    return String(val ?? "");
  }
</script>

<div class="auto-answered-summary">
  <details class="govuk-details" open={expanded}>
    <summary
      class="govuk-details__summary"
      onclick={() => (expanded = !expanded)}
    >
      <span class="govuk-details__summary-text">
        {items.length} question{items.length !== 1 ? "s" : ""} answered automatically
      </span>
    </summary>
    <div class="govuk-details__text">
      {#each items as item}
        <div class="auto-answered-item">
          <p class="govuk-body-s govuk-!-margin-bottom-1">
            <strong>{item.question_text}</strong>
          </p>
          <p class="govuk-body-s govuk-!-margin-bottom-0">
            Answer: {formatValue(item.submitted_value)}
            {#if item.explanation}
              <span style="color: #505a5f;"> — {item.explanation}</span>
            {/if}
          </p>
        </div>
      {/each}
    </div>
  </details>
</div>
