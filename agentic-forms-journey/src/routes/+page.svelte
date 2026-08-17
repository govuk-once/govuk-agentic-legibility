<script lang="ts">
  import { recordTurn, resetRunLog } from "$lib/stores/run-log.svelte";

  type ChatMessage = { role: "user" | "assistant"; content: string };

  // Conversation + agent state. The uploaded form and the whole chat live on the
  // client and are sent to /api/run on each turn.
  let formJson = $state<string | null>(null);
  let formName = $state<string | null>(null);
  let messages = $state<ChatMessage[]>([]);
  let result = $state<any>(null);
  let input = $state("");
  let loading = $state(false);
  let error = $state<string | null>(null);
  let logEl = $state<HTMLDivElement | null>(null);

  type JourneyStep = {
    stage: string;
    status: string;
    decision: string;
    rationale: string;
  };

  const stageOrder = ["discover", "understand", "fill", "validate", "submit"];

  // Formats nullable values for summary tables.
  function metric(value: unknown) {
    return value === undefined || value === null ? "-" : String(value);
  }

  // Formats list values for readable table output.
  function listMetric(value: unknown) {
    if (!Array.isArray(value)) return metric(value);
    if (value.length === 0) return "none";
    return value.join(", ");
  }

  // Finds one stage row from a journey timeline by its stage name.
  function stepForStage(steps: JourneyStep[] | undefined, stage: string): JourneyStep | undefined {
    return steps?.find((step) => step.stage === stage);
  }

  // Maps a journey status to a GOV.UK tag colour modifier.
  function statusTagClass(status: unknown): string {
    switch (status) {
      case "success":
        return "govuk-tag--green";
      case "failed":
        return "govuk-tag--red";
      case "blocked":
        return "govuk-tag--orange";
      default:
        return "govuk-tag--grey";
    }
  }

  // Maps a boolean validity flag to a GOV.UK tag colour modifier.
  function boolTagClass(value: unknown): string {
    if (value === true) return "govuk-tag--green";
    if (value === false) return "govuk-tag--red";
    return "govuk-tag--grey";
  }

  // Tracks which accordion sections are open. Sections start collapsed.
  let expanded = $state<Record<string, boolean>>({
    mapping: false,
    deterministic: false,
    llm: false,
    comparison: false,
    branches: false,
  });

  function toggleSection(key: string) {
    expanded[key] = !expanded[key];
  }

  // Maps a journey-flow state to its GOV.UK tag colour.
  function flowStateTag(state: string): string {
    switch (state) {
      case "answered":
        return "govuk-tag--green";
      case "skipped":
        return "govuk-tag--grey";
      case "undetermined":
        return "govuk-tag--yellow";
      case "unanswered":
        return "govuk-tag--red";
      default:
        return "govuk-tag--grey";
    }
  }

  // Maps a journey-flow state to its human-readable label.
  function flowStateText(state: string): string {
    switch (state) {
      case "unanswered":
        return "needs answer";
      case "answered":
      case "skipped":
      case "undetermined":
        return state;
      default:
        return state;
    }
  }

  // Reads an uploaded GOV form JSON file into memory and resets the conversation.
  async function handleFile(event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    const file = target.files?.[0];
    if (!file) return;

    const text = await file.text();
    try {
      JSON.parse(text);
    } catch {
      error = "That file isn't valid JSON.";
      return;
    }

    formJson = text;
    formName = file.name;
    messages = [];
    result = null;
    error = null;
    resetRunLog();
  }

  // Clears the loaded form so a different one can be uploaded.
  function resetForm() {
    formJson = null;
    formName = null;
    messages = [];
    result = null;
    error = null;
    input = "";
    resetRunLog();
  }

  // Sends the citizen's message to the agent and appends the reply.
  async function send() {
    const content = input.trim();
    if (!formJson || !content || loading) return;

    messages = [...messages, { role: "user", content }];
    input = "";
    loading = true;
    error = null;

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ formJson, messages }),
      });
      const data = await response.json();
      if (data.error) {
        error = data.error;
      } else {
        result = data.result;
        messages = [...messages, { role: "assistant", content: data.result.reply }];

        // Record this turn into the portable run log (viewable at /log).
        recordTurn({
          form: data.result.form ?? { id: "unknown", name: formName },
          conversation: messages,
          user: content,
          agentReply: data.result.reply,
          awaitingInput: data.result.awaitingInput ?? false,
          telemetry: data.result.telemetry ?? {
            model: "unknown",
            latencyMs: 0,
            inputTokens: 0,
            outputTokens: 0,
          },
          flow: data.result.flow ?? [],
          answeredKeys: Object.keys(data.result.llm?.answers ?? {}),
        });
      }
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : "Something went wrong.";
    } finally {
      loading = false;
    }
  }

  function handleChatSubmit(event: SubmitEvent) {
    event.preventDefault();
    send();
  }

  // Keeps the newest message in view as the conversation grows.
  $effect(() => {
    messages.length;
    loading;
    if (logEl) logEl.scrollTop = logEl.scrollHeight;
  });
</script>

<div class="govuk-width-container page-fill">
  <main class="govuk-main-wrapper" id="main-content">
    <h1 class="govuk-heading-l">GOV.UK Forms | Agentic Journey </h1>
    <p class="govuk-body-m">
      Upload a form created and downloaded from <a class="govuk-link" href="https://www.forms.service.gov.uk/" target="_blank">GOV.UK Forms</a>, then ask the agent to complete it for you. The agent
      fills what it can, and asks only for the minimum it still needs.
    </p>


    {#if !formJson}
      <div class="govuk-form-group">
        <label class="govuk-label govuk-label--s" for="formFile">Upload the GOV form JSON</label>
        <input
          class="govuk-input"
          id="formFile"
          type="file"
          accept="application/json"
          onchange={handleFile}
        />
      </div>
    {:else}
      <p class="govuk-body form-loaded">
        Form loaded: <strong>{formName}</strong>
        <button type="button" class="link-button" onclick={resetForm}>Change form</button>
      </p>

      <section class="chat" aria-label="Chat with the agent">
        <div class="chat__log" bind:this={logEl}>
          {#if messages.length === 0}
            <p class="govuk-body chat__hint">
              Tell the agent what you need. For example, “Report a pothole on my street.”
            </p>
          {/if}
          {#each messages as message, i (i)}
            <div class={`chat__msg chat__msg--${message.role}`}>
              <p class="govuk-body chat__bubble">{message.content}</p>
            </div>
          {/each}
          {#if loading}
            <div class="chat__msg chat__msg--assistant">
              <p class="govuk-body chat__bubble chat__bubble--typing">Working on it…</p>
            </div>
          {/if}
        </div>

        <form class="chat__form" onsubmit={handleChatSubmit}>
          <label class="govuk-visually-hidden" for="chatInput">Your message</label>
          <input
            class="govuk-input chat__input"
            id="chatInput"
            type="text"
            bind:value={input}
            placeholder="Ask the agent to complete the form…"
            autocomplete="off"
          />
          <button class="govuk-button chat__send" type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </section>
    {/if}

    {#if error}
      <p class="govuk-error-message">{error}</p>
    {/if}

    {#if result}
      <hr class="govuk-section-break govuk-section-break--l govuk-section-break--visible" />
    <p class="govuk-body-m">
     View the breakdown of the journey and the branch conditions below. The information updates as more details are inferred.
    </p>
    <p class="govuk-body-m">
      <a class="govuk-link" href="/log">View the run log &rarr;</a> &mdash; time, tokens, conversation and agent actions logged for comparison against other methods.
    </p>
      <div class="govuk-accordion" id="results-accordion">
        <!-- Mapping -->
        <div class={`govuk-accordion__section ${expanded.mapping ? "govuk-accordion__section--expanded" : ""}`}>
          {@render accordionHead("mapping", 1, "Mapping")}
          <div
            id="accordion-content-1"
            class="govuk-accordion__section-content"
            role="region"
            aria-labelledby="accordion-heading-1"
            hidden={!expanded.mapping}
          >
            <table class="govuk-table">
              <thead>
                <tr>
                  <th class="govuk-table__header">Question</th>
                  <th class="govuk-table__header">Key</th>
                  <th class="govuk-table__header">Type</th>
                  <th class="govuk-table__header">Required</th>
                  <th class="govuk-table__header">Applies when</th>
                </tr>
              </thead>
              <tbody>
                {#each result.mapping as row (row.key)}
                  <tr>
                    <td class="govuk-table__cell">{row.questionText}</td>
                    <td class="govuk-table__cell"><code>{row.key}</code></td>
                    <td class="govuk-table__cell">{row.answerType}</td>
                    <td class="govuk-table__cell">{row.required ? "yes" : "no"}</td>
                    <td class="govuk-table__cell">{row.appliesWhen ?? "always"}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Deterministic journey -->
        <div class={`govuk-accordion__section ${expanded.deterministic ? "govuk-accordion__section--expanded" : ""}`}>
          {@render accordionHead("deterministic", 2, "Deterministic journey")}
          <div
            id="accordion-content-2"
            class="govuk-accordion__section-content"
            role="region"
            aria-labelledby="accordion-heading-2"
            hidden={!expanded.deterministic}
          >
            <div class="dots">
              {#each result.deterministic.steps as step, i (`det-dot-${step.stage}-${i}`)}
                <span class={`dot ${step.status}`} title={`${step.stage}: ${step.decision}`}></span>
              {/each}
            </div>
            <table class="govuk-table">
              <thead>
                <tr>
                  <th class="govuk-table__header">Stage</th>
                  <th class="govuk-table__header">Status</th>
                  <th class="govuk-table__header">Decision</th>
                  <th class="govuk-table__header">Reason</th>
                </tr>
              </thead>
              <tbody>
                {#each result.deterministic.steps as step, i (`det-row-${step.stage}-${i}`)}
                  <tr>
                    <td class="govuk-table__cell">{step.stage}</td>
                    <td class="govuk-table__cell">
                      <strong class={`govuk-tag ${statusTagClass(step.status)}`}>{step.status}</strong>
                    </td>
                    <td class="govuk-table__cell">{step.decision}</td>
                    <td class="govuk-table__cell">{step.rationale}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- LLM journey -->
        <div class={`govuk-accordion__section ${expanded.llm ? "govuk-accordion__section--expanded" : ""}`}>
          {@render accordionHead("llm", 3, "LLM journey")}
          <div
            id="accordion-content-3"
            class="govuk-accordion__section-content"
            role="region"
            aria-labelledby="accordion-heading-3"
            hidden={!expanded.llm}
          >
            {#if result.llm.fillError}
              <p class="govuk-error-message">{result.llm.fillError}</p>
            {/if}
            <div class="dots">
              {#each result.llm.steps as step, i (`llm-dot-${step.stage}-${i}`)}
                <span class={`dot ${step.status}`} title={`${step.stage}: ${step.decision}`}></span>
              {/each}
            </div>
            <table class="govuk-table">
              <thead>
                <tr>
                  <th class="govuk-table__header">Stage</th>
                  <th class="govuk-table__header">Status</th>
                  <th class="govuk-table__header">Decision</th>
                  <th class="govuk-table__header">Reason</th>
                </tr>
              </thead>
              <tbody>
                {#each result.llm.steps as step, i (`llm-row-${step.stage}-${i}`)}
                  <tr>
                    <td class="govuk-table__cell">{step.stage}</td>
                    <td class="govuk-table__cell">
                      <strong class={`govuk-tag ${statusTagClass(step.status)}`}>{step.status}</strong>
                    </td>
                    <td class="govuk-table__cell">{step.decision}</td>
                    <td class="govuk-table__cell">{step.rationale}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Comparison (stage matrix + missing fields, with headline metrics as tiles) -->
        <div class={`govuk-accordion__section ${expanded.comparison ? "govuk-accordion__section--expanded" : ""}`}>
          {@render accordionHead("comparison", 4, "Comparison")}
          <div
            id="accordion-content-4"
            class="govuk-accordion__section-content"
            role="region"
            aria-labelledby="accordion-heading-4"
            hidden={!expanded.comparison}
          >
            <div class="stats-tiles">
              <div class="stat-tile stat-tile--det">
                <div class="stat-n">{metric(result.compare.detValidationErrorCount)}</div>
                <div class="stat-l">Deterministic errors</div>
              </div>
              <div class="stat-tile stat-tile--llm">
                <div class="stat-n">{metric(result.compare.llmValidationErrorCount)}</div>
                <div class="stat-l">LLM errors</div>
              </div>
              <div class="stat-tile stat-tile--overlap">
                <div class="stat-n">{metric(result.compare.answerOverlap)}</div>
                <div class="stat-l">Answer overlap</div>
              </div>
            </div>

            <table class="govuk-table">
              <thead>
                <tr>
                  <th class="govuk-table__header">Stage</th>
                  <th class="govuk-table__header">Deterministic status</th>
                  <th class="govuk-table__header">LLM status</th>
                  <th class="govuk-table__header">Deterministic note</th>
                  <th class="govuk-table__header">LLM note</th>
                </tr>
              </thead>
              <tbody>
                {#each stageOrder as stage (stage)}
                  {@const detStep = stepForStage(result.deterministic.steps, stage)}
                  {@const llmStep = stepForStage(result.llm.steps, stage)}
                  <tr>
                    <td class="govuk-table__cell">{stage}</td>
                    <td class="govuk-table__cell">
                      {#if detStep?.status}
                        <strong class={`govuk-tag ${statusTagClass(detStep.status)}`}>{detStep.status}</strong>
                      {:else}-{/if}
                    </td>
                    <td class="govuk-table__cell">
                      {#if llmStep?.status}
                        <strong class={`govuk-tag ${statusTagClass(llmStep.status)}`}>{llmStep.status}</strong>
                      {:else}-{/if}
                    </td>
                    <td class="govuk-table__cell">{metric(detStep?.decision)}</td>
                    <td class="govuk-table__cell">{metric(llmStep?.decision)}</td>
                  </tr>
                {/each}
                <tr>
                  <td class="govuk-table__cell">Deterministic missing required fields</td>
                  <td class="govuk-table__cell" colspan="4">
                    {listMetric(result.compare.detMissingRequiredFields)}
                  </td>
                </tr>
                <tr>
                  <td class="govuk-table__cell">LLM missing required fields</td>
                  <td class="govuk-table__cell" colspan="4">
                    {listMetric(result.compare.llmMissingRequiredFields)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Branch conditions (sits directly above the Journey flow it relates to) -->
        <div class={`govuk-accordion__section ${expanded.branches ? "govuk-accordion__section--expanded" : ""}`}>
          {@render accordionHead("branches", 5, "Branch conditions")}
          <div
            id="accordion-content-5"
            class="govuk-accordion__section-content"
            role="region"
            aria-labelledby="accordion-heading-5"
            hidden={!expanded.branches}
          >
            {#if !result.branchRules || result.branchRules.length === 0}
              <p class="govuk-body">No routing rules found.</p>
            {:else}
              <ol class="branch-flow">
                {#each result.branchRules as rule, i (`branch-${rule.questionKey}-${i}`)}
                  <li class="branch-node">
                    <span class="branch-node__dot" aria-hidden="true"></span>
                    <div class="branch-node__body">
                      <p class="govuk-body branch-node__question">{rule.questionText}</p>
                      <p class="govuk-body-s branch-node__rule">
                        <span class="branch-node__label">if answer is</span>
                        <strong class="govuk-tag govuk-tag--blue">{rule.answerValue}</strong>
                        <span class="branch-node__arrow" aria-hidden="true">→</span>
                        <span class="branch-node__label">jump to</span>
                        <strong class="govuk-tag govuk-tag--purple">{rule.jumpTo}</strong>
                      </p>
                      {#if rule.skippedQuestionTexts.length > 0}
                        <p class="govuk-body-s branch-node__skips">
                          Skips: {rule.skippedQuestionTexts.join(", ")}
                        </p>
                      {/if}
                    </div>
                  </li>
                {/each}
              </ol>
            {/if}
          </div>
        </div>
      </div>

      <section>
        <h2 class="govuk-heading-m">Journey flow</h2>
        <p class="govuk-body-m flow-intro">
          The whole question order, top to bottom, with every branch point. Each step shows what the
          agent answered, the answer that decided the route, and where a human should confirm before
          the route can be trusted.
        </p>

        <ul class="flow-legend">
          <li><span class="govuk-tag govuk-tag--green">answered</span></li>
          <li><span class="govuk-tag govuk-tag--grey">skipped</span></li>
          <li><span class="govuk-tag govuk-tag--yellow">undetermined</span></li>
          <li><span class="govuk-tag govuk-tag--red">needs answer</span></li>
          <li><span class="govuk-tag govuk-tag--orange">human check</span></li>
        </ul>

        <ol class="flow">
          {#each result.flow as node (node.key)}
            <li class="flow-node">
              <span class="flow-node__marker">{node.order}</span>
              <div class="flow-node__card">
                <h3 class="govuk-heading-s flow-node__title">{node.questionText}</h3>

                <p class="govuk-body flow-node__meta">
                  {node.answerType} · {node.required ? "required" : "optional"}{node.isDecision
                    ? " · decision point"
                    : ""}
                </p>

                <div class="flow-result">
                  <p class="flow-result__head">
                    <span class={`govuk-tag ${flowStateTag(node.status.state)}`}>
                      {flowStateText(node.status.state)}
                    </span>
                    {#if node.status.needsHuman}
                      <span class="govuk-tag govuk-tag--orange">human check</span>
                    {/if}
                  </p>

                  {#if node.status.state === "answered"}
                    {#if node.isDecision}
                      <!-- Resolved decision: the answer given, then the route it produced. -->
                      <p class="govuk-body flow-result__line">
                        <span class="flow-result__k">answer</span>
                        <strong class="govuk-tag govuk-tag--blue">{node.status.answer}</strong>
                      </p>
                      {#if node.status.routeTaken}
                        <p class="govuk-body flow-result__line">
                          <span class="flow-result__k">route</span>
                          {node.status.routeTaken}
                        </p>
                      {/if}
                    {:else}
                      <p class="govuk-body flow-result__line">
                        <span class="flow-result__k">answer</span>
                        {node.status.answer}
                      </p>
                    {/if}
                  {:else if node.isDecision && node.status.state === "unanswered"}
                    <!-- Pending decision: show the choices and where each would route. -->
                    {#if node.options.length > 0}
                      <div class="flow-block">
                        <span class="govuk-body flow-block__label">Options</span>
                        <span class="flow-block__tags">
                          {#each node.options as option (option)}
                            <span class="govuk-tag govuk-tag--blue">{option}</span>
                          {/each}
                        </span>
                      </div>
                    {/if}
                    <div class="flow-block">
                      <span class="govuk-body flow-block__label">Branching</span>
                      <ul class="flow-routes">
                        {#each node.routes as route (route.answerValue)}
                          <li class="flow-route">
                            <span class="flow-route__line">
                              <span class="govuk-body flow-route__k">if</span>
                              <strong class="govuk-tag govuk-tag--blue">{route.answerValue}</strong>
                            </span>
                            <span class="flow-route__line">
                              <span class="govuk-body flow-route__k">jump to</span>
                              <strong class="govuk-tag govuk-tag--purple">{route.jumpTo}</strong>
                            </span>
                            {#if route.skippedQuestionTexts.length > 0}
                              <span class="govuk-body flow-route__skips">
                                skips {route.skippedQuestionTexts.join(", ")}
                              </span>
                            {/if}
                          </li>
                        {/each}
                      </ul>
                    </div>
                    {#if node.status.note}
                      <p class="govuk-body flow-result__note">{node.status.note}</p>
                    {/if}
                  {:else if node.status.note}
                    <p class="govuk-body flow-result__note">{node.status.note}</p>
                  {/if}
                </div>
              </div>
            </li>
          {/each}
        </ol>
      </section>
    {/if}
  </main>

{#snippet accordionHead(key: string, num: number, title: string)}
  <div class="govuk-accordion__section-header">
    <h2 class="govuk-accordion__section-heading">
      <button
        type="button"
        class="govuk-accordion__section-button"
        id={`accordion-heading-${num}`}
        aria-controls={`accordion-content-${num}`}
        aria-expanded={expanded[key]}
        onclick={() => toggleSection(key)}
      >
        <span class="govuk-accordion__section-heading-text">
          <span class="govuk-accordion__section-heading-text-focus">{title}</span>
        </span>
        <span class="govuk-accordion__section-toggle">
          <span class="govuk-accordion__section-toggle-focus">
            <span
              class={`govuk-accordion-nav__chevron ${expanded[key] ? "" : "govuk-accordion-nav__chevron--down"}`}
            ></span>
            <span class="govuk-accordion__section-toggle-text">{expanded[key] ? "Hide" : "Show"}</span>
          </span>
        </span>
      </button>
    </h2>
  </div>
{/snippet}
</div>

<style>
  /* Grow to fill the viewport so the initial
     short page pushes the footer to the bottom. */
  .page-fill {
    flex: 1 0 auto;
  }

  /* ---- Upload + chat ---- */
  .form-loaded {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 12px;
  }

  .link-button {
    background: none;
    border: 0;
    padding: 0;
    font: inherit;
    color: #1d70b8;
    text-decoration: underline;
    cursor: pointer;
  }

  .link-button:hover {
    color: #003078;
  }

  .chat {
    border: 1px solid #b1b4b6;
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 20px;
  }

  .chat__log {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-height: 420px;
    overflow-y: auto;
    padding: 16px;
    background: #f8f8f8;
  }

  .chat__hint {
    margin: 0;
    color: #505a5f;
  }

  .chat__msg {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 80%;
  }

  .chat__msg--user {
    align-self: flex-end;
    align-items: flex-end;
  }

  .chat__msg--assistant {
    align-self: flex-start;
    align-items: flex-start;
  }

  .chat__bubble {
    margin: 0;
    padding: 10px 14px;
    border-radius: 12px;
    background: #ffffff;
    border: 1px solid #b1b4b6;
    white-space: pre-wrap;
  }

  .chat__msg--user .chat__bubble {
    background: #1d70b8;
    border-color: #1d70b8;
    color: #ffffff;
  }

  .chat__bubble--typing {
    color: #505a5f;
  }

  .chat__form {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    border-top: 1px solid #b1b4b6;
    background: #ffffff;
  }

  .chat__input {
    flex: 1;
    margin: 0;
  }

  .chat__send {
    flex: 0 0 auto;
    margin: 0;
  }

  .dots {
    display: flex;
    gap: 0.4rem;
    margin: 0.4rem 0 1rem;
    flex-wrap: wrap;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }

  .dot.success {
    background: #00703c;
  }

  .dot.failed {
    background: #d4351c;
  }

  .dot.blocked {
    background: #f47738;
  }

  /* Headline comparison metrics as tiles above the comparison table. */
  .stats-tiles {
    display: flex;
    align-items: stretch;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 20px;
  }

  .stat-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-width: 84px;
    padding: 12px 16px;
    background: #f3f2f1;
  }

  .stat-tile--det {
    background: #cfe4dc;
  }

  .stat-tile--llm {
    background: #fde4d7;
  }

  .stat-n {
    font-family: "GDS Transport", arial, sans-serif;
    font-weight: 400;
    font-size: 1.75rem;
    line-height: 1;
    color: #0b0c0c;
  }

  .stat-tile--det .stat-n {
    color: #083d29;
  }

  .stat-tile--llm .stat-n {
    color: #7a3c1c;
  }

  .stat-l {
    font-family: "GDS Transport", arial, sans-serif;
    font-weight: 400;
    font-size: 0.75rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #505a5f;
    text-align: center;
    max-width: 6.5em;
  }

  /* Vertical branch/condition flow — one node per routing rule. */
  .branch-flow {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .branch-node {
    position: relative;
    padding: 0 0 24px 32px;
  }

  .branch-node:last-child {
    padding-bottom: 0;
  }

  /* Connector line joining consecutive nodes. */
  .branch-node::before {
    content: "";
    position: absolute;
    left: 8px;
    top: 6px;
    bottom: 0;
    width: 2px;
    background: #b1b4b6;
  }

  .branch-node:last-child::before {
    display: none;
  }

  /* Node marker. */
  .branch-node__dot {
    position: absolute;
    left: 0;
    top: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #1d70b8;
    box-shadow: 0 0 0 3px #fff;
  }

  .branch-node__body {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .branch-node__question {
    margin: 0;
    font-weight: 700;
  }

  .branch-node__rule {
    margin: 0;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .branch-node__label {
    color: #505a5f;
  }

  .branch-node__arrow {
    color: #505a5f;
    font-weight: 700;
  }

  .branch-node__skips {
    margin: 0;
    color: #505a5f;
  }

  /* ---- Journey flow: one shared vertical spine, both runs annotated ---- */
  .flow-intro {
    color: #505a5f;
    max-width: 40em;
  }

  .flow-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    list-style: none;
    margin: 0 0 20px;
    padding: 0;
  }

  .flow {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .flow-node {
    position: relative;
    padding: 0 0 20px 50px;
  }

  /* One continuous spine, centred under the numbered markers. */
  .flow-node::before {
    content: "";
    position: absolute;
    left: 16px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #b1b4b6;
  }

  .flow-node:last-child::before {
    display: none;
  }

  /* Numbered GOV.UK-blue marker sitting on the spine. */
  .flow-node__marker {
    position: absolute;
    left: 0;
    top: 0;
    z-index: 1;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: #1d70b8;
    color: #ffffff;
    font-family: "GDS Transport", arial, sans-serif;
    font-weight: bold;
    font-size: 16px;
    line-height: 34px;
    text-align: center;
  }

  .flow-node__card {
    border: 1px solid #b1b4b6;
    border-radius: 4px;
    padding: 12px 14px;
    background: #ffffff;
  }

  .flow-node__title {
    margin: 0;
  }

  .flow-node__meta {
    color: #505a5f;
    margin: 6px 0 0;
  }

  /* Each labelled block stacks its label above its value. */
  .flow-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 14px;
  }

  .flow-block__label {
    font-weight: 700;
    color: #505a5f;
    margin: 0;
  }

  .flow-block__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .flow-routes {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .flow-route {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-left: 12px;
    border-left: 3px solid #b1b4b6;
  }

  .flow-route__line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .flow-route__k,
  .flow-result__k {
    color: #505a5f;
  }

  .flow-route__skips {
    color: #505a5f;
    margin: 0;
  }

  .flow-result {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 16px;
    border-top: 1px solid #f3f2f1;
    padding-top: 14px;
  }

  .flow-result__head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 0;
  }

  .flow-result__line {
    margin: 0;
  }

  .flow-result__note {
    margin: 0;
    color: #505a5f;
  }
</style>
