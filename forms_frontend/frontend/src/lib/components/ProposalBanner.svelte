<script lang="ts">
  import type { Proposal } from "../api";

  interface Props {
    proposal: Proposal;
    onConfirm: () => void;
    onReject: () => void;
    submitting: boolean;
  }

  let { proposal, onConfirm, onReject, submitting }: Props = $props();

  function formatValue(val: any): string {
    if (val === true) return "Yes";
    if (val === false) return "No";
    if (Array.isArray(val)) return val.join(", ");
    return String(val ?? "");
  }
</script>

<div class="proposal-banner" role="region" aria-label="Suggested answer">
  <h3 class="govuk-heading-s proposal-banner__heading">
    The assistant suggests an answer
  </h3>

  <p class="govuk-body">
    <strong>Suggested answer:</strong> {formatValue(proposal.value)}
  </p>

  {#if proposal.explanation}
    <p class="govuk-body-s" style="color: #505a5f;">
      {proposal.explanation}
    </p>
  {/if}

  <div style="display: flex; gap: 10px; margin-top: 10px;">
    <button
      class="govuk-button"
      onclick={onConfirm}
      disabled={submitting}
    >
      Accept and continue
    </button>
    <button
      class="govuk-button govuk-button--secondary"
      onclick={onReject}
      disabled={submitting}
    >
      Edit answer
    </button>
  </div>
</div>
