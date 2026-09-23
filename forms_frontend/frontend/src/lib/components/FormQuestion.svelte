<script lang="ts">
  import {
    submitAnswer,
    confirmProposal,
    rejectProposal,
    requestProposal,
    streamAutoProgress,
    uploadFile,
    type AwaitingInput,
    type Presentation,
    type Proposal,
    type AutoProgressEvent,
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
  import { createProposalAttemptGate } from "../proposalAttemptGate.js";
  import { onDestroy } from "svelte";

  interface Props {
    sessionId: string;
    awaiting: AwaitingInput;
    presentation: Presentation | null;
    pendingProposal: Proposal | null;
    policy: string;
    autoAnsweredCount: number;
    onSubmitted: () => void | Promise<void>;
    onComplete: () => void;
  }

  let {
    sessionId,
    awaiting,
    presentation,
    pendingProposal,
    policy,
    autoAnsweredCount,
    onSubmitted,
    onComplete,
  }: Props = $props();

  let value: any = $state(null);
  let submitting = $state(false);
  let validationError = $state("");
  let proposalLoading = $state(false);
  const proposalGate = createProposalAttemptGate();
  let autoPausedForUser = $state(false);
  let autoProgressError = $state("");
  let activeStream: ReturnType<typeof streamAutoProgress> | null = null;

  // Auto-progress streaming state
  interface ProgressStep {
    question: string;
    value: string;
    explanation: string;
  }
  let autoProgressActive = $state(false);
  let autoProgressSteps: ProgressStep[] = $state([]);
  let autoProgressCurrent = $state("");
  let autoProgressTotal = $state(0);
  let autoProgressDone = $state(0);

  const pres = $derived(presentation ?? awaiting.schema?.presentation ?? null);
  const answerType = $derived(pres?.answer_type ?? "text");
  const answerSettings = $derived(pres?.answer_settings ?? {});
  const questionText = $derived(pres?.question_text ?? awaiting.prompt);
  const hintText = $derived(pres?.hint_text ?? null);
  const isOptional = $derived(pres?.is_optional ?? awaiting.schema?.allow_skip ?? false);
  const kind = $derived(awaiting.schema?.kind ?? "string");
  const options = $derived(awaiting.schema?.options ?? awaiting.options ?? []);

  $effect(() => {
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

  // Attempt each token once, regardless of how often the parent refreshes the
  // same Temporal state. In auto mode a "needs_input" response pauses the agent
  // until the user supplies the missing answer (or explicitly retries).
  $effect(() => {
    const token = awaiting?.token;
    if (
      !autoPausedForUser &&
      !pendingProposal &&
      !proposalLoading &&
      !autoProgressActive &&
      !submitting &&
      proposalGate.claim(sessionId, token, policy)
    ) {
      if (policy === "auto") {
        startAutoProgress();
      } else if (policy === "confirm") {
        requestProposalNow();
      }
    }
  });

  // Closing the stream also stops processing its events after a policy switch
  // or after navigating away. The API separately checks policy before submit.
  $effect(() => {
    if (policy !== "auto" && activeStream) {
      activeStream.close();
      activeStream = null;
      autoProgressActive = false;
      autoProgressCurrent = "";
    }
  });

  onDestroy(() => activeStream?.close());

  function startAutoProgress() {
    autoProgressActive = true;
    autoProgressError = "";
    autoProgressSteps = [];
    autoProgressCurrent = "";
    autoProgressTotal = 0;
    // SSE reports cumulative automatic answers. Do not reset a 7/11 journey
    // to 0/11 when it resumes after a question answered manually.
    autoProgressDone = autoAnsweredCount;

    activeStream = streamAutoProgress(
      sessionId,
      (event: AutoProgressEvent) => {
        if (event.total_questions != null) {
          autoProgressTotal = event.total_questions;
        }

        if (event.type === "waiting") {
          autoProgressCurrent = event.question ?? "";
        } else if (event.type === "step") {
          autoProgressDone = event.steps_taken ?? autoProgressDone + 1;
          autoProgressSteps = [
            ...autoProgressSteps,
            {
              question: event.question ?? "",
              value: event.value ?? "",
              explanation: event.explanation ?? "",
            },
          ];
          autoProgressCurrent = "";
        } else if (event.type === "done") {
          activeStream?.close();
          activeStream = null;
          autoProgressActive = false;
          autoProgressCurrent = "";
          autoProgressDone = event.steps_taken ?? autoProgressDone;
          if (event.reason !== "complete") {
            // The question reached by the server may have a *new* token;
            // simply remembering the token that started the SSE is insufficient.
            autoPausedForUser = true;
          }
          if (event.reason === "error") {
            autoProgressError = "Automatic completion stopped. Please answer this question yourself.";
          }
          void onSubmitted();
        }
      },
      () => {
        activeStream?.close();
        activeStream = null;
        autoProgressActive = false;
        autoProgressCurrent = "";
        autoPausedForUser = true;
        autoProgressError = "Automatic completion was interrupted. You can answer the question below.";
        void onSubmitted();
      }
    );
  }

  function retryAutomaticCompletion() {
    proposalGate.retry(sessionId, awaiting.token, "auto");
    autoPausedForUser = false;
    autoProgressError = "";
  }

  async function requestProposalNow() {
    proposalLoading = true;
    try {
      const result = await requestProposal(sessionId);
      if (result.has_answer) {
        onSubmitted();
        return;
      }
    } catch (e) {
      console.error("Proposal request failed:", e);
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

    if (isOptional && (value === null || value === "" || value === undefined)) {
      if (awaiting.schema?.allow_skip) {
        submitValue = kind === "file_ref" ? null : (awaiting.schema.default ?? "");
      } else {
        submitValue = "";
      }
    }

    submitting = true;
    try {
      if (kind === "file_ref" && value instanceof File) {
        submitValue = await uploadFile(sessionId, awaiting.token, value);
      }
      const result = await submitAnswer(sessionId, awaiting.token, submitValue);
      if (result.status === "COMPLETED") {
        onComplete();
      } else {
        // Wait for the parent to receive the NEW Temporal awaiting token before
        // resuming auto mode. Otherwise the old question can be retried.
        await onSubmitted();
        autoPausedForUser = false;
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

  function formatValue(val: string): string {
    if (val === "true") return "Yes";
    if (val === "false") return "No";
    return val;
  }
</script>

{#if autoProgressActive || autoProgressSteps.length > 0}
  <div class="auto-progress" role="status" aria-live="polite">
    <h2 class="govuk-heading-m">
      {#if autoProgressActive}
        Completing form automatically...
      {:else}
        The assistant answered {autoProgressDone} question{autoProgressDone !== 1 ? "s" : ""}
      {/if}
    </h2>

    {#if autoProgressActive && autoProgressTotal > 0}
      <div class="govuk-!-margin-bottom-4">
        <div class="progress-bar" role="progressbar"
          aria-valuenow={autoProgressDone}
          aria-valuemin={0}
          aria-valuemax={autoProgressTotal}
          aria-label="Form progress"
        >
          <div
            class="progress-bar__fill"
            style="width: {Math.round((autoProgressDone / autoProgressTotal) * 100)}%"
          ></div>
        </div>
        <p class="govuk-body-s govuk-!-margin-top-1" style="color: #505a5f;">
          {autoProgressDone} of {autoProgressTotal} questions
        </p>
      </div>
    {/if}

    {#if autoProgressSteps.length > 0}
      <table class="govuk-table govuk-table--small-text-until-tablet">
        <thead class="govuk-table__head">
          <tr class="govuk-table__row">
            <th scope="col" class="govuk-table__header">Question</th>
            <th scope="col" class="govuk-table__header">Answer</th>
          </tr>
        </thead>
        <tbody class="govuk-table__body">
          {#each autoProgressSteps as step}
            <tr class="govuk-table__row">
              <td class="govuk-table__cell">{step.question}</td>
              <td class="govuk-table__cell">
                <strong>{formatValue(step.value)}</strong>
                {#if step.explanation}
                  <br /><span class="govuk-body-s" style="color: #505a5f;">{step.explanation}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    {#if autoProgressActive && autoProgressCurrent}
      <div class="govuk-inset-text govuk-!-margin-top-2 govuk-!-margin-bottom-0">
        Reviewing: <strong>{autoProgressCurrent}</strong>
      </div>
    {/if}
  </div>

  {#if !autoProgressActive}
    <hr class="govuk-section-break govuk-section-break--l govuk-section-break--visible" />
  {/if}
{/if}

{#if autoPausedForUser && policy === "auto" && !autoProgressActive}
  <div class="govuk-inset-text" role="status">
    <p class="govuk-body">
      <strong>The assistant needs your help with this question.</strong>
    </p>
    <p class="govuk-body-s">Answer below to continue. Automatic completion will resume with the next question.</p>
    {#if autoProgressError}
      <p class="govuk-body-s">{autoProgressError}</p>
    {/if}
    <button type="button" class="govuk-button govuk-button--secondary" onclick={retryAutomaticCompletion}>
      Try automatic completion again
    </button>
  </div>
{/if}

{#if proposalLoading}
  <div class="govuk-inset-text" role="status" aria-live="polite">
    <p class="govuk-body">
      <strong>The assistant is reviewing this question...</strong>
    </p>
    <p class="govuk-body-s" style="color: #505a5f;">
      Checking whether an answer can be suggested from the conversation.
    </p>
  </div>
{:else if !autoProgressActive}
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
        <Radios
          name="question-input"
          label={questionText}
          hint={hintText}
          {isOptional}
          options={options.map((o) => ({ value: o.value, label: o.label }))}
          bind:value
          error={validationError}
        />
      {:else if kind === "file_ref"}
        <div class="govuk-form-group">
          <label class="govuk-label govuk-label--m" for="question-input">{questionText}</label>
          {#if hintText}<div class="govuk-hint">{hintText}</div>{/if}
          <input class="govuk-file-upload" type="file" id="question-input"
            onchange={(event) => { value = event.currentTarget.files?.[0] ?? null; }} />
          {#if isOptional}<p class="govuk-hint">You can skip this question.</p>{/if}
          <p class="govuk-hint">Local prototype only: maximum 10 MiB. Use synthetic files.</p>
        </div>
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
{/if}

<style>
  .auto-progress {
    background-color: #f3f2f1;
    border-left: 4px solid #1d70b8;
    padding: 20px;
    margin-bottom: 20px;
  }

  .progress-bar {
    height: 20px;
    background-color: #dee0e2;
    border-radius: 0;
    overflow: hidden;
  }

  .progress-bar__fill {
    height: 100%;
    background-color: #00703c;
    transition: width 0.4s ease;
  }
</style>
