<script lang="ts">
  import {
    listForms,
    startSession,
    getSessionState,
    setPolicy,
    type FormSummary,
    type SessionState,
  } from "./lib/api";
  import FormQuestion from "./lib/components/FormQuestion.svelte";
  import ChatPanel from "./lib/components/ChatPanel.svelte";
  import FormComplete from "./lib/components/FormComplete.svelte";
  import AutoProgressLog from "./lib/components/AutoProgressLog.svelte";

  type View = "list" | "form" | "complete";

  let view: View = $state("list");
  let forms: FormSummary[] = $state([]);
  let sessionId: string = $state("");
  let sessionState: SessionState | null = $state(null);
  let formName: string = $state("");
  let loading: boolean = $state(false);
  let error: string = $state("");
  let policy: string = $state("manual");

  async function loadForms() {
    loading = true;
    error = "";
    try {
      forms = await listForms();
    } catch (e: any) {
      error = e.message || "Failed to load forms";
    } finally {
      loading = false;
    }
  }

  async function handleStartForm(formId: string | number) {
    loading = true;
    error = "";
    try {
      const session = await startSession(formId, policy);
      sessionId = session.session_id;
      formName = session.form_name;
      const state = await getSessionState(sessionId);
      sessionState = state;
      view = "form";
    } catch (e: any) {
      error = e.message || "Failed to start form";
    } finally {
      loading = false;
    }
  }

  async function refreshState() {
    if (!sessionId) return;
    try {
      sessionState = await getSessionState(sessionId);
      if (sessionState?.status === "COMPLETED") {
        view = "complete";
      }
    } catch (e: any) {
      error = e.message;
    }
  }

  async function handlePolicyChange(newPolicy: string) {
    policy = newPolicy;
    if (sessionId) {
      await setPolicy(sessionId, newPolicy);
      sessionState = await getSessionState(sessionId);
    }
  }

  function handleComplete() {
    view = "complete";
  }

  function handleBackToList() {
    view = "list";
    sessionId = "";
    sessionState = null;
    formName = "";
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

    {#if view === "list"}
      <h1 class="govuk-heading-xl">Available forms</h1>

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
              The agent automatically submits answers it's confident about, skipping questions it can answer.
            {/if}
          </div>
        </fieldset>
      </div>

      {#if loading}
        <p class="govuk-body">Loading forms...</p>
      {:else if forms.length === 0}
        <p class="govuk-body">
          No forms available. Ensure the workflow definition server is running.
        </p>
      {:else}
        <table class="govuk-table">
          <thead class="govuk-table__head">
            <tr class="govuk-table__row">
              <th scope="col" class="govuk-table__header">Form ID</th>
              <th scope="col" class="govuk-table__header">Name</th>
              <th scope="col" class="govuk-table__header">Action</th>
            </tr>
          </thead>
          <tbody class="govuk-table__body">
            {#each forms as form}
              <tr class="govuk-table__row">
                <td class="govuk-table__cell">{form.id}</td>
                <td class="govuk-table__cell">{form.name || form.slug || "—"}</td>
                <td class="govuk-table__cell">
                  <button
                    class="govuk-button govuk-button--secondary"
                    onclick={() => handleStartForm(form.id)}
                    disabled={loading}
                  >
                    Start
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}

    {:else if view === "form"}
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

          {#if sessionState?.auto_answered && sessionState.auto_answered.length > 0}
            <AutoProgressLog items={sessionState.auto_answered} />
          {/if}

          {#if sessionState?.awaiting}
            <FormQuestion
              {sessionId}
              awaiting={sessionState.awaiting}
              presentation={sessionState.presentation}
              pendingProposal={sessionState.pending_proposal}
              {policy}
              onSubmitted={refreshState}
              onComplete={handleComplete}
            />
          {:else if sessionState?.status === "COMPLETED"}
            <FormComplete metadata={sessionState.form_metadata} onBack={handleBackToList} />
          {:else}
            <p class="govuk-body">Waiting for the next question...</p>
          {/if}
        </div>

        <div>
          <ChatPanel {sessionId} onStateChange={refreshState} />
        </div>
      </div>

    {:else if view === "complete"}
      <FormComplete
        metadata={sessionState?.form_metadata ?? null}
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
