<script lang="ts">
  import { submitAnswer, type AwaitingInput } from "../api";

  interface Props {
    sessionId: string;
    awaiting: AwaitingInput;
    pendingTransition: boolean;
    onSubmitted: (afterToken?: string) => void | Promise<void>;
    onComplete: () => void | Promise<void>;
  }

  let { sessionId, awaiting, pendingTransition, onSubmitted, onComplete }: Props = $props();
  let submitting = $state(false);
  let error = $state("");

  async function choosePayment(simulateSuccess: boolean) {
    if (submitting || pendingTransition) return;
    submitting = true;
    error = "";
    try {
      // This is the compiler's ordinary Boolean InputState. No payment API,
      // external URL, card details or monetary transaction is involved.
      const result = await submitAnswer(sessionId, awaiting.token, simulateSuccess);
      if (result.status === "COMPLETED") {
        await onComplete();
      } else {
        await onSubmitted(awaiting.token);
      }
    } catch (e: any) {
      error = e.message || "Could not record your simulated payment choice";
    } finally {
      submitting = false;
    }
  }
</script>

<h2 class="govuk-heading-l">Simulated payment</h2>
<div class="govuk-inset-text">
  <strong>This is a prototype, not a real payment page.</strong>
  <p class="govuk-body govuk-!-margin-top-2 govuk-!-margin-bottom-0">
    No money will be taken. No application will be submitted to a department.
    Do not enter any payment or card details.
  </p>
</div>
<p class="govuk-body">
  You can simulate a successful payment to finish this prototype journey, or cancel.
</p>
{#if error}
  <div class="govuk-error-summary" role="alert">
    <h3 class="govuk-error-summary__title">There is a problem</h3>
    <p class="govuk-error-summary__body">{error}</p>
  </div>
{/if}
<div class="govuk-button-group">
  <button type="button" class="govuk-button" disabled={submitting || pendingTransition}
    onclick={() => void choosePayment(true)}>
    {submitting ? "Recording choice..." : "Simulate successful payment"}
  </button>
  <button type="button" class="govuk-button govuk-button--secondary"
    disabled={submitting || pendingTransition} onclick={() => void choosePayment(false)}>
    Cancel simulated payment
  </button>
</div>
