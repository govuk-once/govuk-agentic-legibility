<script lang="ts">
  import {
    listForms,
    listFixtures,
    getFixture,
    startSession,
    getSessionState,
    setPolicy,
    type FormSummary,
    type SessionState,
    type ConversationFixture,
    type ConversationFixtureDetail,
  } from "./lib/api";
  import FormQuestion from "./lib/components/FormQuestion.svelte";
  import ChatPanel from "./lib/components/ChatPanel.svelte";
  import FormComplete from "./lib/components/FormComplete.svelte";
  import AutoProgressLog from "./lib/components/AutoProgressLog.svelte";
  import ReviewAnswers from "./lib/components/ReviewAnswers.svelte";
  import { sessionView, waitForCompletion, reviewAcknowledged } from "./lib/sessionView.js";

  type View = "list" | "form" | "review" | "complete";

  let view: View = $state("list");
  let forms: FormSummary[] = $state([]);
  let fixtures: ConversationFixture[] = $state([]);
  let sessionId: string = $state("");
  let sessionState: SessionState | null = $state(null);
  let formName: string = $state("");
  let loading: boolean = $state(false);
  let error: string = $state("");
  let policy: string = $state("manual");
  let reviewBeforeSubmit = $state(true);
  let selectedFixtureId: string = $state("");
  let fixturePreview: ConversationFixtureDetail | null = $state(null);
  let preloadedConversation: Array<{ role: string; content: string }> = $state([]);
  let transitionPending = $state(false);
  let pendingPreviousToken: string | undefined = $state(undefined);
  let pendingRefreshError = $state("");
  let refreshInFlight: Promise<void> | null = null;
  let completionExpected = $state(false);
  // An authoritative terminal/review state takes precedence over a previous
  // component's route. Never fall back to a stale question at completion.
  const displayView: View = $derived(sessionView(view, sessionState));

  async function loadForms() {
    loading = true;
    error = "";
    try {
      forms = await listForms();
    } catch (e: any) {
      error = e.message || "Failed to load forms";
    }
    try {
      fixtures = await listFixtures();
    } catch {
      fixtures = [];
    }
    loading = false;
  }

  function extractNumericId(formId: string | number): string {
    const s = String(formId);
    const match = s.match(/(\d+)$/);
    return match ? match[1] : s;
  }

  function fixturesForForm(formId: string | number): ConversationFixture[] {
    const numericId = extractNumericId(formId);
    return fixtures.filter((f) => {
      const fixtureNumeric = extractNumericId(f.form_id ?? "");
      return fixtureNumeric === numericId;
    });
  }

  async function handleFixtureSelect(fixtureId: string) {
    selectedFixtureId = fixtureId;
    fixturePreview = null;
    if (fixtureId) {
      try {
        fixturePreview = await getFixture(fixtureId);
      } catch {
        fixturePreview = null;
      }
    }
  }

  async function handleStartForm(formId: string | number) {
    loading = true;
    error = "";
    try {
      const requestedReview = policy === "auto" && reviewBeforeSubmit;
      const session = await startSession(formId, policy, selectedFixtureId || null, requestedReview);
      if (!reviewAcknowledged(requestedReview, session.review_before_submit)) {
        throw new Error("The Forms API did not enable final review. Restart the Forms API after applying the patch, then start a new form.");
      }
      completionExpected = false;
      sessionId = session.session_id;
      formName = session.form_name;

      if (fixturePreview?.conversation) {
        preloadedConversation = fixturePreview.conversation;
      } else {
        preloadedConversation = [];
      }

      const state = await getSessionState(sessionId);
      sessionState = state;
      view = state.review_required ? "review" : state.status === "COMPLETED" ? "complete" : "form";
    } catch (e: any) {
      error = e.message || "Failed to start form";
    } finally {
      loading = false;
    }
  }

  function refreshState(afterToken?: string, expectCompleted = false): Promise<void> {
    // SSE completion and the manual form can both request a refresh. Never let
    // one response overwrite a later authoritative state with a stale token.
    const requestedSession = sessionId;
    if (!requestedSession) return Promise.resolve();
    if (expectCompleted) completionExpected = true;
    if (afterToken) pendingPreviousToken = afterToken;
    if (afterToken || completionExpected) transitionPending = true;
    // A manual submit can overlap the SSE's final refresh. The in-flight poll
    // must use the newly accepted token instead of accepting its old snapshot.
    if (refreshInFlight) return refreshInFlight;
    pendingRefreshError = "";
    const task = (async () => {
      const deadline = Date.now() + 15000;
      while (sessionId === requestedSession) {
        const next = await getSessionState(requestedSession);
        const stillAdvancing = waitForCompletion(next, completionExpected, pendingPreviousToken);
        if (!stillAdvancing) {
          sessionState = next;
          transitionPending = false;
          pendingPreviousToken = undefined;
          completionExpected = false;
          if (next.status === "COMPLETED") view = next.review_required ? "review" : "complete";
          else view = "form";
          return;
        }
        transitionPending = true;
        if (Date.now() >= deadline) {
          pendingRefreshError = "Your answer was accepted, but the next step is not ready. Check progress; do not submit again.";
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
    })().catch((e: any) => {
      error = e.message || "Unable to check journey progress";
      throw e;
    }).finally(() => { refreshInFlight = null; });
    refreshInFlight = task;
    return task;
  }

  async function handlePolicyChange(newPolicy: string) {
    const previous = policy;
    if (!sessionId) {
      policy = newPolicy;
      return;
    }
    try {
      const requestedReview = newPolicy === "auto" && reviewBeforeSubmit;
      const updated = await setPolicy(sessionId, newPolicy, requestedReview);
      if (!reviewAcknowledged(requestedReview, updated.review_before_submit)) {
        throw new Error("The Forms API did not acknowledge the review setting. Restart the API.");
      }
      sessionState = await getSessionState(sessionId);
      policy = newPolicy;
      error = "";
    } catch (e: any) {
      // Keep the displayed mode in sync with the actual server policy. For
      // action-bearing journeys final review is intentionally unavailable.
      policy = previous;
      error = e.message || "Unable to change interaction policy";
    }
  }

  async function handleReviewChange(updated: SessionState) {
    sessionState = updated;
    transitionPending = false;
    pendingPreviousToken = undefined;
    completionExpected = false;
    view = sessionView("form", updated);
  }

  async function handleReviewToggle(checked: boolean) {
    const previous = reviewBeforeSubmit;
    reviewBeforeSubmit = checked;
    if (sessionId) {
      try {
        const updated = await setPolicy(sessionId, policy, checked);
        if (!reviewAcknowledged(checked, updated.review_before_submit)) {
          throw new Error("The Forms API did not acknowledge the review setting. Restart the API.");
        }
        sessionState = await getSessionState(sessionId);
      } catch (e: any) {
        reviewBeforeSubmit = previous;
        error = e.message || "Unable to change review settings";
      }
    }
  }

  async function handleComplete() {
    // The last accepted input, or the SSE's terminal event, is authoritative
    // evidence that completion is expected. Do not render an old question
    // while the subsequent Temporal query catches up.
    await refreshState(undefined, true);
  }

  function handleBackToList() {
    view = "list";
    sessionId = "";
    sessionState = null;
    formName = "";
    selectedFixtureId = "";
    fixturePreview = null;
    preloadedConversation = [];
    transitionPending = false;
    pendingPreviousToken = undefined;
    pendingRefreshError = "";
    completionExpected = false;
  }

  $effect(() => {
    if (view === "list") {
      loadForms();
    }
  });
</script>

<a href="#main-content" class="govuk-skip-link" data-module="govuk-skip-link"
  >Skip to main content</a
>

<header class="govuk-header" data-module="govuk-header">
  <div class="govuk-header__container govuk-width-container">
    <div class="govuk-header__logo">
      <span class="govuk-header__logotype">
        <span class="govuk-header__logotype-text">GOV.UK</span>
      </span>
    </div>
    <div class="govuk-header__content">
      <a href="/" class="govuk-header__link govuk-header__service-name" onclick={(e) => { e.preventDefault(); handleBackToList(); }}>
        Forms
      </a>
    </div>
  </div>
</header>

<div class="govuk-width-container">
  <div class="govuk-phase-banner">
    <p class="govuk-phase-banner__content">
      <strong class="govuk-tag govuk-phase-banner__content__tag">Prototype</strong>
      <span class="govuk-phase-banner__text">
        This is an experimental GOV.UK Forms frontend with agentic assistance.
      </span>
    </p>
  </div>

  <main class="govuk-main-wrapper" id="main-content">
    {#if error}
      <div class="govuk-error-summary" data-module="govuk-error-summary">
        <div role="alert">
          <h2 class="govuk-error-summary__title">There is a problem</h2>
          <div class="govuk-error-summary__body">
            <p>{error}</p>
          </div>
        </div>
      </div>
    {/if}

    {#if displayView === "list"}
      <h1 class="govuk-heading-xl">Available forms</h1>

      <div class="govuk-grid-row">
        <div class="govuk-grid-column-two-thirds">

          <div class="govuk-form-group" style="margin-bottom: 30px;">
            <fieldset class="govuk-fieldset">
              <legend class="govuk-fieldset__legend govuk-fieldset__legend--s">
                Interaction policy
              </legend>
              <div class="policy-switcher">
                <button
                  class="policy-btn"
                  class:policy-btn--active={policy === "manual"}
                  onclick={() => (policy = "manual")}
                >
                  Manual
                </button>
                <button
                  class="policy-btn"
                  class:policy-btn--active={policy === "confirm"}
                  onclick={() => (policy = "confirm")}
                >
                  Confirm
                </button>
                <button
                  class="policy-btn"
                  class:policy-btn--active={policy === "auto"}
                  onclick={() => (policy = "auto")}
                >
                  Automatic
                </button>
              </div>
              <div class="govuk-hint">
                {#if policy === "manual"}
                  You complete the form normally. The agent can answer questions but won't fill in answers.
                {:else if policy === "confirm"}
                  The agent proposes answers from the conversation. You confirm or edit before submission.
                {:else}
                  The assistant fills in answers it knows and asks you for any missing details.
                {/if}
              </div>
              {#if policy === "auto"}
                <div class="govuk-checkboxes govuk-checkboxes--small govuk-!-margin-top-3">
                  <div class="govuk-checkboxes__item">
                    <input class="govuk-checkboxes__input" id="initial-final-review" type="checkbox"
                      checked={reviewBeforeSubmit}
                      onchange={(e) => (reviewBeforeSubmit = e.currentTarget.checked)} />
                    <label class="govuk-label govuk-checkboxes__label" for="initial-final-review">
                      Let me check all answers before submitting
                    </label>
                  </div>
                </div>
                <p class="govuk-hint govuk-!-margin-top-2">Review and change any answers when the assistant has finished.</p>
              {/if}
            </fieldset>
          </div>

          {#if loading}
            <p class="govuk-body">Loading forms...</p>
          {:else if forms.length === 0}
            <p class="govuk-body">
              No forms available. Ensure the workflow definition server is running.
            </p>
          {:else}
            {#each forms as form}
              {@const formFixtures = fixturesForForm(form.id)}
              <div class="govuk-summary-card" style="margin-bottom: 20px;">
                <div class="govuk-summary-card__title-wrapper">
                  <h2 class="govuk-summary-card__title">{form.name || form.slug || `Form ${form.id}`}</h2>
                  <div class="govuk-summary-card__actions">
                    <span class="govuk-body-s" style="color: #505a5f;">ID: {form.id}</span>
                  </div>
                </div>
                <div class="govuk-summary-card__content">
                  {#if formFixtures.length > 0}
                    <div class="govuk-form-group" style="margin-bottom: 15px;">
                      <label class="govuk-label govuk-label--s" for="fixture-{form.id}">
                        Conversation history
                      </label>
                      <div class="govuk-hint">
                        Pre-load a conversation so the agent already knows the user's details.
                      </div>
                      <select
                        class="govuk-select"
                        id="fixture-{form.id}"
                        onchange={(e) => handleFixtureSelect((e.target as HTMLSelectElement).value)}
                      >
                        <option value="">No conversation history</option>
                        {#each formFixtures as fx}
                          <option value={fx.id}>{fx.title} ({fx.message_count} messages)</option>
                        {/each}
                      </select>
                    </div>

                    {#if fixturePreview && selectedFixtureId && formFixtures.some(f => f.id === selectedFixtureId)}
                      <details class="govuk-details" style="margin-bottom: 15px;">
                        <summary class="govuk-details__summary">
                          <span class="govuk-details__summary-text">Preview conversation</span>
                        </summary>
                        <div class="govuk-details__text">
                          <p class="govuk-body-s" style="color: #505a5f; margin-bottom: 10px;">
                            {fixturePreview.description}
                          </p>
                          {#each fixturePreview.conversation as msg}
                            <div class="chat-message chat-message--{msg.role}" style="margin-bottom: 8px; padding: 8px; font-size: 14px;">
                              <strong>{msg.role === "user" ? "User" : "Assistant"}:</strong>
                              {msg.content}
                            </div>
                          {/each}
                        </div>
                      </details>
                    {/if}
                  {:else}
                    <p class="govuk-body-s" style="color: #505a5f;">
                      No conversation fixtures available for this form.
                    </p>
                  {/if}

                  <button
                    class="govuk-button"
                    data-module="govuk-button"
                    onclick={() => handleStartForm(form.id)}
                    disabled={loading}
                  >
                    Start form
                    {#if selectedFixtureId && formFixtures.some(f => f.id === selectedFixtureId)}
                      with conversation
                    {/if}
                  </button>
                </div>
              </div>
            {/each}
          {/if}
        </div>

        <div class="govuk-grid-column-one-third">
          <div style="background-color: #f3f2f1; padding: 15px; border-left: 4px solid #1d70b8;">
            <h3 class="govuk-heading-s">How it works</h3>
            <p class="govuk-body-s">
              Select a form and optionally load a conversation history.
              The conversation gives the agent context about the user's situation.
            </p>
            <p class="govuk-body-s">
              <strong>Manual:</strong> Answer every question yourself.
              The chat is available for help.
            </p>
            <p class="govuk-body-s">
              <strong>Confirm:</strong> The agent proposes answers
              from the conversation. You review each one.
            </p>
            <p class="govuk-body-s">
              <strong>Automatic:</strong> The assistant fills in answers
              it knows and asks for missing information. You can choose
              to review all answers at the end.
            </p>
          </div>
        </div>
      </div>

    {:else if displayView === "form"}
      <div class="forms-layout">
        <div>
          <a
            href="/"
            class="govuk-back-link"
            onclick={(e) => { e.preventDefault(); handleBackToList(); }}
          >
            Back to form list
          </a>

          <h1 class="govuk-heading-l">{formName}</h1>

          <div class="policy-switcher" style="margin-bottom: 20px;">
            <button
              class="policy-btn"
              class:policy-btn--active={policy === "manual"}
              onclick={() => handlePolicyChange("manual")}
            >Manual</button>
            <button
              class="policy-btn"
              class:policy-btn--active={policy === "confirm"}
              onclick={() => handlePolicyChange("confirm")}
            >Confirm</button>
            <button
              class="policy-btn"
              class:policy-btn--active={policy === "auto"}
              onclick={() => handlePolicyChange("auto")}
            >Auto</button>
          </div>
          {#if policy === "auto"}
            <div class="govuk-checkboxes govuk-checkboxes--small govuk-!-margin-bottom-4">
              <div class="govuk-checkboxes__item">
                <input class="govuk-checkboxes__input" id="active-final-review" type="checkbox"
                  checked={reviewBeforeSubmit}
                  onchange={(e) => void handleReviewToggle(e.currentTarget.checked)} />
                <label class="govuk-label govuk-checkboxes__label" for="active-final-review">
                  Let me check all answers before submitting
                </label>
              </div>
            </div>
          {/if}

          {#if sessionState?.auto_answered && sessionState.auto_answered.length > 0 && !sessionState.review_required}
            <AutoProgressLog items={sessionState.auto_answered} />
          {/if}

          {#if transitionPending}
            <div class="govuk-inset-text" role="status" aria-live="polite">
              Your answer has been accepted. Waiting for the next question or completion.
              {#if pendingRefreshError}
                <p class="govuk-body">{pendingRefreshError}</p>
                <button type="button" class="govuk-button govuk-button--secondary"
                  onclick={() => void refreshState(pendingPreviousToken, completionExpected)}>Check progress</button>
              {/if}
            </div>
          {/if}

          {#if sessionState?.review_required}
            <ReviewAnswers {sessionId} state={sessionState}
              onStateChange={handleReviewChange} onComplete={handleComplete} />
          {:else if sessionState?.awaiting}
            <FormQuestion
              {sessionId}
              awaiting={sessionState.awaiting}
              presentation={sessionState.presentation}
              pendingProposal={sessionState.pending_proposal}
              {policy}
              answeredCount={sessionState.answered_count ?? sessionState.auto_answered.length}
              pendingTransition={transitionPending}
              forceManualHandoff={sessionState.review_replay_needs_input}
              onSubmitted={refreshState}
              onComplete={handleComplete}
            />
          {:else if sessionState?.status === "COMPLETED"}
            <FormComplete metadata={sessionState.form_metadata}
              transcript={sessionState.transcript ?? []} result={sessionState.result}
              autoAnswered={sessionState.auto_answered}
              onBack={handleBackToList} />
          {:else}
            <p class="govuk-body">Waiting for the next question...</p>
          {/if}
        </div>

        <div>
          <ChatPanel {sessionId} {preloadedConversation} onStateChange={refreshState} />
        </div>
      </div>

    {:else if displayView === "review" && sessionState?.review_required}
      <h1 class="govuk-heading-l">{formName}</h1>
      <ReviewAnswers {sessionId} state={sessionState}
        onStateChange={handleReviewChange} onComplete={handleComplete} />
    {:else if displayView === "complete"}
      <FormComplete
        metadata={sessionState?.form_metadata ?? null}
        transcript={sessionState?.transcript ?? []}
        result={sessionState?.result}
        autoAnswered={sessionState?.auto_answered ?? []}
        onBack={handleBackToList}
      />
    {/if}
  </main>
</div>

<footer class="govuk-footer">
  <div class="govuk-width-container">
    <div class="govuk-footer__meta">
      <div class="govuk-footer__meta-item govuk-footer__meta-item--grow">
        <span class="govuk-footer__licence-description">
          Prototype — not a real government service
        </span>
      </div>
      <div class="govuk-footer__meta-item">
        <a
          class="govuk-footer__link govuk-footer__copyright-logo"
          href="https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/uk-government-licensing-framework/crown-copyright/"
        >
          &copy; Crown copyright
        </a>
      </div>
    </div>
  </div>
</footer>
