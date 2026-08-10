<script lang="ts">
  import { runLogStore } from "$lib/stores/run-log.svelte";
  import type { AgentActionKind, RunLog } from "$lib/run-log";

  // The log accumulates on the home page and is mirrored to sessionStorage,
  // so it is available here after navigation or a refresh.
  const log = $derived(runLogStore.log);

  // Maps an agent action to a GOV.UK tag colour.
  function actionTag(action: AgentActionKind): string {
    switch (action) {
      case "filled":
        return "govuk-tag--green";
      case "skipped":
        return "govuk-tag--grey";
      case "undetermined":
        return "govuk-tag--yellow";
      default:
        return "govuk-tag--red";
    }
  }

  function actionLabel(action: AgentActionKind): string {
    return action === "needs-answer" ? "needs answer" : action;
  }

  // Presents milliseconds as a compact "1.2s" / "840ms" label.
  function ms(value: number): string {
    if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
    return `${Math.round(value)}ms`;
  }

  // The conversation history is also shown row-by-row in the interaction table,
  // so here it is offered purely as a copy/paste artifact: one readable block in
  // either plain text or JSON, ready to drop into a reference elsewhere.
  let convoFormat = $state<"text" | "json">("text");
  let copied = $state(false);

  const conversationString = $derived.by(() => {
    if (!log) return "";
    if (convoFormat === "json") {
      return JSON.stringify(log.criteria.conversationHistory, null, 2);
    }
    return log.criteria.conversationHistory
      .map((message) => `${message.role === "user" ? "Citizen" : "Agent"}: ${message.content}`)
      .join("\n\n");
  });

  // Legacy copy path for when the async Clipboard API is unavailable or blocked
  // (older browsers, missing permission, no document focus).
  function fallbackCopy(text: string) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  async function copyConversation() {
    const text = conversationString;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy(text);
      }
      copied = true;
    } catch {
      try {
        fallbackCopy(text);
        copied = true;
      } catch {
        copied = false;
      }
    }
    if (copied) setTimeout(() => (copied = false), 2000);
  }

  // Optional human-friendly name for this run, saved into the export so the
  // comparison page can label it meaningfully (e.g. "Parking permit v1").
  let exportTitle = $state("");

  // Serialises the log (stamped with an export time) and downloads it as JSON,
  // ready to be compared against logs from other methods.
  function exportJson() {
    if (!log) return;
    const title = exportTitle.trim();
    const payload: RunLog = {
      ...log,
      title: title || log.title,
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `run-log-${log.method}-${log.form.id}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
</script>

<div class="govuk-width-container page-fill">
  <main class="govuk-main-wrapper" id="main-content">
    <a class="govuk-back-link" href="/">Back to the form</a>

    <h1 class="govuk-heading-l">Run log</h1>
    <p class="govuk-body-m">
      Criteria captured for this agent run so it can be compared, like-for-like, against other
      agentic form-filling methods.
    </p>
    <p class="govuk-body-m">
      <a class="govuk-link" href="/compare">Compare against other methods &rarr;</a>
    </p>

    {#if !log}
      <div class="govuk-inset-text">
        No run recorded yet. Upload a form on the <a class="govuk-link" href="/">home page</a> and
        send the agent a message, then come back here.
      </div>
    {:else}
      <dl class="govuk-summary-list">
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Method</dt>
          <dd class="govuk-summary-list__value"><code>{log.method}</code></dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Model</dt>
          <dd class="govuk-summary-list__value"><code>{log.model}</code></dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Form</dt>
          <dd class="govuk-summary-list__value">
            {log.form.name ?? "(unnamed)"} <span class="govuk-hint">{log.form.id}</span>
          </dd>
        </div>
      </dl>

      <div class="govuk-form-group export-name">
        <label class="govuk-label govuk-label--s" for="exportTitle">Name this run (optional)</label>
        <div id="exportTitle-hint" class="govuk-hint">
          Shown as the label on the compare page, so you can tell runs apart. For example, “Parking permit v1”.
        </div>
        <input
          class="govuk-input"
          id="exportTitle"
          type="text"
          bind:value={exportTitle}
          aria-describedby="exportTitle-hint"
          placeholder="e.g. Parking permit v1"
        />
      </div>
      <button type="button" class="govuk-button govuk-button--secondary" onclick={exportJson}>
        Export JSON
      </button>

      <!-- 1. Time / tokens -->
      <h2 class="govuk-heading-m">1. Time &amp; tokens</h2>
      <dl class="govuk-summary-list govuk-summary-list--no-border metric-grid">
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Turns</dt>
          <dd class="govuk-summary-list__value">{log.criteria.performance.totals.turns}</dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Input tokens</dt>
          <dd class="govuk-summary-list__value">{log.criteria.performance.totals.inputTokens}</dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Output tokens</dt>
          <dd class="govuk-summary-list__value">{log.criteria.performance.totals.outputTokens}</dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Total tokens</dt>
          <dd class="govuk-summary-list__value">{log.criteria.performance.totals.totalTokens}</dd>
        </div>
        <div class="govuk-summary-list__row">
          <dt class="govuk-summary-list__key">Wall time</dt>
          <dd class="govuk-summary-list__value">{ms(log.criteria.performance.totals.wallMs)}</dd>
        </div>
      </dl>

      <table class="govuk-table">
        <caption class="govuk-table__caption govuk-table__caption--s">Per turn</caption>
        <thead class="govuk-table__head">
          <tr class="govuk-table__row">
            <th class="govuk-table__header">Turn</th>
            <th class="govuk-table__header govuk-table__header--numeric">Input</th>
            <th class="govuk-table__header govuk-table__header--numeric">Output</th>
            <th class="govuk-table__header govuk-table__header--numeric">Latency</th>
          </tr>
        </thead>
        <tbody class="govuk-table__body">
          {#each log.criteria.performance.turns as t (t.turn)}
            <tr class="govuk-table__row">
              <td class="govuk-table__cell">{t.turn}</td>
              <td class="govuk-table__cell govuk-table__cell--numeric">{t.inputTokens}</td>
              <td class="govuk-table__cell govuk-table__cell--numeric">{t.outputTokens}</td>
              <td class="govuk-table__cell govuk-table__cell--numeric">{ms(t.latencyMs)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <!-- 2. Conversation history: collapsed copy/paste artifact. The same
           exchange is broken down visually in the interaction table below. -->
      <h2 class="govuk-heading-m">2. Conversation history</h2>
      <details class="govuk-details">
        <summary class="govuk-details__summary">
          <span class="govuk-details__summary-text">Show full transcript (copy &amp; paste)</span>
        </summary>
        <div class="govuk-details__text">
          <div class="convo-toolbar">
            <div class="convo-formats" role="group" aria-label="Transcript format">
              <button
                type="button"
                class={`convo-format ${convoFormat === "text" ? "convo-format--active" : ""}`}
                aria-pressed={convoFormat === "text"}
                onclick={() => (convoFormat = "text")}
              >
                Text
              </button>
              <button
                type="button"
                class={`convo-format ${convoFormat === "json" ? "convo-format--active" : ""}`}
                aria-pressed={convoFormat === "json"}
                onclick={() => (convoFormat = "json")}
              >
                JSON
              </button>
            </div>
            <button
              type="button"
              class="govuk-button govuk-button--secondary convo-copy"
              onclick={copyConversation}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre class="convo-pre">{conversationString}</pre>
        </div>
      </details>

      <!-- 3. Conversation during interaction -->
      <h2 class="govuk-heading-m">3. Conversation during interaction</h2>
      <table class="govuk-table">
        <thead class="govuk-table__head">
          <tr class="govuk-table__row">
            <th class="govuk-table__header">Turn</th>
            <th class="govuk-table__header">Citizen said</th>
            <th class="govuk-table__header">Agent replied</th>
            <th class="govuk-table__header">Asked for more?</th>
            <th class="govuk-table__header">New fields</th>
          </tr>
        </thead>
        <tbody class="govuk-table__body">
          {#each log.criteria.interaction as row (row.turn)}
            <tr class="govuk-table__row">
              <td class="govuk-table__cell">{row.turn}</td>
              <td class="govuk-table__cell">{row.user}</td>
              <td class="govuk-table__cell">{row.agent}</td>
              <td class="govuk-table__cell">
                <strong class={`govuk-tag ${row.awaitingInput ? "govuk-tag--yellow" : "govuk-tag--green"}`}>
                  {row.awaitingInput ? "asked" : "no"}
                </strong>
              </td>
              <td class="govuk-table__cell">
                {row.newFields.length > 0 ? row.newFields.join(", ") : "-"}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>

      <!-- 4. Things the agent does -->
      <h2 class="govuk-heading-m">4. Things the agent does</h2>
      <table class="govuk-table">
        <thead class="govuk-table__head">
          <tr class="govuk-table__row">
            <th class="govuk-table__header">Question</th>
            <th class="govuk-table__header">Action</th>
            <th class="govuk-table__header">Detail</th>
            <th class="govuk-table__header">Needs a human?</th>
          </tr>
        </thead>
        <tbody class="govuk-table__body">
          {#each log.criteria.agentActions as action (action.field)}
            <tr class="govuk-table__row">
              <td class="govuk-table__cell">{action.questionText}</td>
              <td class="govuk-table__cell">
                <strong class={`govuk-tag ${actionTag(action.action)}`}>{actionLabel(action.action)}</strong>
              </td>
              <td class="govuk-table__cell">{action.detail || "-"}</td>
              <td class="govuk-table__cell">{action.needsHuman ? "yes" : "no"}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <!-- 5. Executor actions (reserved) -->
      <h2 class="govuk-heading-m">5. Executor actions</h2>
      <div class="govuk-inset-text">
        {log.criteria.executorActions.note}
      </div>
    {/if}
  </main>
</div>

<style>
  .metric-grid :global(.govuk-summary-list__key) {
    width: 40%;
  }

  .export-name {
    max-width: 30rem;
  }

  .convo-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }

  .convo-formats {
    display: inline-flex;
  }

  .convo-format {
    border: 1px solid #b1b4b6;
    background: #ffffff;
    padding: 0.25rem 0.85rem;
    font: inherit;
    line-height: 1.5;
    cursor: pointer;
  }

  .convo-format + .convo-format {
    border-left: 0;
  }

  .convo-format--active {
    background: #1d70b8;
    border-color: #1d70b8;
    color: #ffffff;
  }

  .convo-copy {
    margin-bottom: 0;
  }

  .convo-pre {
    margin: 0;
    padding: 0.75rem;
    background: #f3f2f1;
    border: 1px solid #b1b4b6;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.875rem;
    line-height: 1.5;
  }
</style>
