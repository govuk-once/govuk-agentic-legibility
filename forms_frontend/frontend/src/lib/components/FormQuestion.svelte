<script lang="ts">
  import {
    submitAnswer,
    confirmProposal,
    rejectProposal,
    requestProposal,
    type AwaitingInput,
    type Presentation,
    type Proposal,
  } from "../api";
  import TextInput from "./inputs/TextInput.svelte";
  import Textarea from "./inputs/Textarea.svelte";
  import Radios from "./inputs/Radios.svelte";
  import DateInput from "./inputs/DateInput.svelte";
  import NameInput from "./inputs/NameInput.svelte";
  import AddressInput from "./inputs/AddressInput.svelte";
  import EmailInput from "./inputs/EmailInput.svelte";
  import NumberInput from "./inputs/NumberInput.svelte";
  import NiNumberInput from "./inputs/NiNumberInput.svelte";
  import ProposalBanner from "./ProposalBanner.svelte";

  interface Props {
    sessionId: string;
    awaiting: AwaitingInput;
    presentation: Presentation | null;
    pendingProposal: Proposal | null;
    policy: string;
    onSubmitted: () => void;
    onComplete: () => void;
  }

  let {
    sessionId,
    awaiting,
    presentation,
    pendingProposal,
    policy,
    onSubmitted,
    onComplete,
  }: Props = $props();

  let value: any = $state(null);
  let submitting = $state(false);
  let validationError = $state("");
  let proposalLoading = $state(false);

  const pres = $derived(presentation ?? awaiting.schema?.presentation ?? null);
  const answerType = $derived(pres?.answer_type ?? "text");
  const answerSettings = $derived(pres?.answer_settings ?? {});
  const questionText = $derived(pres?.question_text ?? awaiting.prompt);
  const hintText = $derived(pres?.hint_text ?? null);
  const isOptional = $derived(pres?.is_optional ?? awaiting.schema?.allow_skip ?? false);
  const kind = $derived(awaiting.schema?.kind ?? "string");
  const options = $derived(awaiting.schema?.options ?? awaiting.options ?? []);

  $effect(() => {
    // Reset value when question changes
    if (awaiting?.token) {
      if (pendingProposal?.value != null) {
        value = pendingProposal.value;
      } else if (awaiting.schema?.default !== undefined) {
        value = awaiting.schema.default;
      } else {
        value = kind === "boolean" ? null : "";
      }
      validationError = "";
    }
  });

  $effect(() => {
    // Auto-request proposal in confirm/auto mode
    if (policy !== "manual" && !pendingProposal && sessionId && awaiting?.token) {
      requestProposalIfNeeded();
    }
  });

  async function requestProposalIfNeeded() {
    if (proposalLoading) return;
    proposalLoading = true;
    try {
      const proposal = await requestProposal(sessionId);
      if (proposal.has_answer) {
        onSubmitted();
      }
    } catch {
      // Proposal failed — user answers manually
    } finally {
      proposalLoading = false;
    }
  }

  async function handleSubmit() {
    validationError = "";

    if (!isOptional && (value === null || value === "" || value === undefined)) {
      validationError = "This field is required";
      return;
    }

    let submitValue = value;

    // Skip handling: if optional and empty, submit the skip token or empty string
    if (isOptional && (value === null || value === "" || value === undefined)) {
      if (awaiting.schema?.allow_skip) {
        submitValue = awaiting.schema.default ?? "";
      } else {
        submitValue = "";
      }
    }

    submitting = true;
    try {
      const result = await submitAnswer(sessionId, awaiting.token, submitValue);
      if (result.status === "COMPLETED") {
        onComplete();
      } else {
        onSubmitted();
      }
    } catch (e: any) {
      validationError = e.message || "Failed to submit answer";
    } finally {
      submitting = false;
    }
  }

  async function handleConfirmProposal() {
    submitting = true;
    try {
      const result = await confirmProposal(sessionId);
      if (result.status === "COMPLETED") {
        onComplete();
      } else {
        onSubmitted();
      }
    } catch (e: any) {
      validationError = e.message || "Failed to confirm proposal";
    } finally {
      submitting = false;
    }
  }

  async function handleRejectProposal() {
    await rejectProposal(sessionId);
    onSubmitted();
  }
</script>

<div class="govuk-form-group" class:govuk-form-group--error={!!validationError}>
  {#if pres?.guidance_markdown}
    <details class="govuk-details">
      <summary class="govuk-details__summary">
        <span class="govuk-details__summary-text">Help with this question</span>
      </summary>
      <div class="govuk-details__text">
        {pres.guidance_markdown}
      </div>
    </details>
  {/if}

  {#if pendingProposal?.has_answer && policy === "confirm"}
    <ProposalBanner
      proposal={pendingProposal}
      onConfirm={handleConfirmProposal}
      onReject={handleRejectProposal}
      {submitting}
    />
  {/if}

  {#if validationError}
    <div class="govuk-error-summary" data-module="govuk-error-summary" role="alert">
      <h2 class="govuk-error-summary__title">There is a problem</h2>
      <div class="govuk-error-summary__body">
        <ul class="govuk-list govuk-error-summary__list">
          <li><a href="#question-input">{validationError}</a></li>
        </ul>
      </div>
    </div>
  {/if}

  <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
    {#if kind === "boolean"}
      <Radios
        name="question-input"
        label={questionText}
        hint={hintText}
        {isOptional}
        options={[
          { value: "true", label: "Yes" },
          { value: "false", label: "No" },
        ]}
        bind:value
        error={validationError}
      />
    {:else if kind === "select_one"}
      <Radios
        name="question-input"
        label={questionText}
        hint={hintText}
        {isOptional}
        options={options.filter((o) => o.value !== "__forms_skip__").map((o) => ({
          value: o.value,
          label: o.label,
        }))}
        bind:value
        error={validationError}
      />
    {:else if kind === "select_many"}
      <!-- Checkboxes for multi-select — simplified to radios for POC -->
      <Radios
        name="question-input"
        label={questionText}
        hint={hintText}
        {isOptional}
        options={options.map((o) => ({ value: o.value, label: o.label }))}
        bind:value
        error={validationError}
      />
    {:else if answerType === "name"}
      <NameInput
        label={questionText}
        hint={hintText}
        settings={answerSettings}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "date"}
      <DateInput
        label={questionText}
        hint={hintText}
        settings={answerSettings}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "address"}
      <AddressInput
        label={questionText}
        hint={hintText}
        settings={answerSettings}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "email"}
      <EmailInput
        label={questionText}
        hint={hintText}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "national_insurance_number"}
      <NiNumberInput
        label={questionText}
        hint={hintText}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "number"}
      <NumberInput
        label={questionText}
        hint={hintText}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else if answerType === "text" && answerSettings?.input_type === "long_text"}
      <Textarea
        name="question-input"
        label={questionText}
        hint={hintText}
        {isOptional}
        bind:value
        error={validationError}
      />
    {:else}
      <TextInput
        name="question-input"
        label={questionText}
        hint={hintText}
        {isOptional}
        bind:value
        error={validationError}
      />
    {/if}

    <div style="margin-top: 20px;">
      <button
        class="govuk-button"
        data-module="govuk-button"
        type="submit"
        disabled={submitting}
      >
        {#if submitting}
          Submitting...
        {:else if isOptional && (value === null || value === "" || value === undefined)}
          Skip this question
        {:else}
          Continue
        {/if}
      </button>
    </div>
  </form>
</div>
