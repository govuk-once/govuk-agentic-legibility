<script lang="ts">
  import { onMount } from "svelte";
  import { runLogStore } from "$lib/stores/run-log.svelte";
  import { parseRunLog, type AgentActionKind, type RunLog } from "$lib/run-log";
  import { SAMPLE_METHODS } from "$lib/fixtures";
  import { deriveComparators } from "$lib/variants";
  import {
    buildDivergence,
    buildScorecard,
    defaultReference,
    groupByForm,
    methodMetrics,
    type Method,
  } from "$lib/compare-metrics";

  let methods = $state<Method[]>([]);
  let importError = $state<string | null>(null);
  // Neutral feedback (not an error) — e.g. an imported file was already loaded.
  let importNotice = $state<string | null>(null);
  let activeFormId = $state<string | null>(null);
  let referenceId = $state<string | null>(null);
  let glanceMetric = $state<"tokens" | "turns" | "questions" | "filled" | "fill">("tokens");

  onMount(() => {
    if (runLogStore.log) addLog(runLogStore.log);
  });

  // A globally-unique key for a method. The display label stays the plain method
  // name; labels only need to be unique within one form, and one form is shown
  // at a time, so the same name on two different forms is fine.
  function uniqueId(log: RunLog): string {
    const base = `${log.method}::${log.form.id}`;
    const existing = new Set(methods.map((m) => m.id));
    if (!existing.has(base)) return base;
    let n = 2;
    while (existing.has(`${base}#${n}`)) n += 1;
    return `${base}#${n}`;
  }

  // Adds a log unless an identical one is already loaded. Returns true if it
  // was added, false if it was skipped as a duplicate (so callers can tell the
  // user rather than fail silently).
  function addLog(log: RunLog): boolean {
    const duplicate = methods.some(
      (m) =>
        m.log.method === log.method &&
        m.log.form.id === log.form.id &&
        m.log.criteria.performance.totals.totalTokens === log.criteria.performance.totals.totalTokens &&
        m.log.criteria.interaction.length === log.criteria.interaction.length,
    );
    if (duplicate) return false;
    methods = [...methods, { id: uniqueId(log), label: makeLabel(log), log }];
    return true;
  }

  // A display label that is unique WITHIN its form group. Prefers the run's
  // own title (set at export) so runs are recognisable, falling back to the
  // method name. Two runs that resolve to the same label on the same form get a
  // suffix to tell them apart; the same label across different forms does not
  // (those never appear side by side).
  function makeLabel(log: RunLog): string {
    const base = log.title?.trim() || log.method;
    const sameForm = methods.filter((m) => m.log.form.id === log.form.id);
    const existing = new Set(sameForm.map((m) => m.label));
    if (!existing.has(base)) return base;
    let n = 2;
    while (existing.has(`${base} (${n})`)) n += 1;
    return `${base} (${n})`;
  }

  function loadSamples() {
    for (const log of SAMPLE_METHODS) addLog(log);
  }

  // Builds synthetic verbose + aggressive comparators from a real run, on the
  // same form, so a single real log has something to compare against.
  function generateComparators(base: RunLog) {
    for (const log of deriveComparators(base)) addLog(log);
  }

  function removeMethod(id: string) {
    methods = methods.filter((m) => m.id !== id);
  }

  function clearAll() {
    methods = [];
    importError = null;
    importNotice = null;
  }

  async function handleImport(event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    const files = target.files ? Array.from(target.files) : [];
    importError = null;
    importNotice = null;
    const errors: string[] = [];
    const skipped: string[] = [];
    for (const file of files) {
      try {
        const log = parseRunLog(JSON.parse(await file.text()));
        if (!addLog(log)) skipped.push(file.name);
      } catch (error) {
        const detail = error instanceof Error ? error.message.split("\n")[0] : "unknown error";
        errors.push(`${file.name}: ${detail}`);
      }
    }
    if (errors.length > 0) importError = errors.join(" · ");
    if (skipped.length > 0) {
      const these = skipped.length === 1 ? "This file is" : "These files are";
      importNotice = `${these} already loaded, so nothing was added: ${skipped.join(", ")}.`;
    }
    target.value = "";
  }

  // Methods can only be compared within one form. Group them, then work inside
  // the active group (default: the largest).
  const formGroups = $derived(groupByForm(methods));
  const activeGroup = $derived(
    formGroups.find((g) => g.formId === activeFormId) ?? formGroups[0] ?? null,
  );
  const otherGroups = $derived(formGroups.filter((g) => g !== activeGroup));

  // Reference (baseline for divergence) within the active group, by id.
  const activeReference = $derived.by(() => {
    const groupMethods = activeGroup?.methods ?? [];
    if (referenceId && groupMethods.some((m) => m.id === referenceId)) return referenceId;
    return defaultReference(groupMethods);
  });

  // Active methods, reference first.
  const orderedMethods = $derived.by<Method[]>(() => {
    const groupMethods = activeGroup?.methods ?? [];
    const ref = groupMethods.find((m) => m.id === activeReference);
    return ref ? [ref, ...groupMethods.filter((m) => m.id !== activeReference)] : groupMethods;
  });

  const scorecard = $derived(orderedMethods.length > 0 ? buildScorecard(orderedMethods) : null);
  const divergence = $derived(buildDivergence(orderedMethods, activeReference));

  const scorecardGroups = $derived.by(() => {
    if (!scorecard) return [];
    const out: { name: string; rows: typeof scorecard.rows }[] = [];
    for (const row of scorecard.rows) {
      let g = out.find((x) => x.name === row.group);
      if (!g) {
        g = { name: row.group, rows: [] };
        out.push(g);
      }
      g.rows.push(row);
    }
    return out;
  });

  // "At a glance" bar chart data for the chosen headline metric.
  const glanceOptions = {
    tokens: {
      label: "Total tokens",
      explain: "Total tokens the method spent (its LLM cost).",
      format: (v: number) => v.toLocaleString(),
    },
    turns: {
      label: "Conversation turns",
      explain: "Number of back-and-forth exchanges (one = the citizen sends a message and the agent replies).",
      format: (v: number) => String(v),
    },
    questions: {
      label: "Questions asked of the human",
      explain: "How many turns the agent had to ask the citizen for more information.",
      format: (v: number) => String(v),
    },
    filled: {
      label: "Filled by the agent",
      explain: "Fields the agent filled in. Which of those still need a human to confirm is shown in “What each method did”.",
      format: (v: number) => String(v),
    },
    fill: {
      label: "Left for a human to fill in",
      explain: "Fields the agent could not complete (e.g. an upload), left for a human to provide.",
      format: (v: number) => String(v),
    },
  } as const;

  const glance = $derived.by(() => {
    const rows = orderedMethods.map((m) => {
      const mm = methodMetrics(m.log);
      const value =
        glanceMetric === "tokens"
          ? mm.totalTokens
          : glanceMetric === "turns"
            ? mm.turns
            : glanceMetric === "questions"
              ? mm.questionsAsked
              : glanceMetric === "filled"
                ? mm.fieldsFilled
                : mm.fieldsToFillByHuman;
      return { id: m.id, label: m.label, value };
    });
    const max = Math.max(1, ...rows.map((r) => r.value));
    return { rows, max };
  });

  function isReference(id: string): boolean {
    return id === activeReference;
  }

  function actionTag(action: AgentActionKind | null): string {
    switch (action) {
      case "filled":
        return "govuk-tag--green";
      case "skipped":
        return "govuk-tag--grey";
      case "undetermined":
        return "govuk-tag--yellow";
      case "needs-answer":
        return "govuk-tag--red";
      default:
        return "govuk-tag--grey";
    }
  }

  function actionLabel(action: AgentActionKind | null): string {
    if (action === null) return "not seen";
    return action === "needs-answer" ? "needs answer" : action;
  }
</script>

<div class="govuk-width-container page-fill cmp">
  <main class="govuk-main-wrapper" id="main-content">
    <a class="govuk-back-link" href="/log">Back to the run log</a>

    <h1 class="govuk-heading-l">Compare methods</h1>
    <p class="govuk-body">
      Put different form-filling methods side by side. Methods can only be compared when they ran the
      <strong>same form</strong> (same questions, same branching), so the page compares one form at a
      time. Load the sample methods to see how it works, or import run logs of your own.
    </p>

    <div class="cmp-controls">
      <button type="button" class="govuk-button govuk-button--secondary" onclick={loadSamples}>
        Load sample methods
      </button>
      <label class="govuk-button govuk-button--secondary cmp-import">
        Import log(s)…
        <input class="cmp-import__input" type="file" accept="application/json" multiple onchange={handleImport} />
      </label>
      {#if methods.length > 0}
        <button type="button" class="govuk-button govuk-button--warning" onclick={clearAll}>Clear all</button>
      {/if}
    </div>

    {#if importError}
      <p class="govuk-error-message">{importError}</p>
    {/if}

    {#if importNotice}
      <div class="govuk-inset-text cmp-notice" role="status">{importNotice}</div>
    {/if}

    {#if methods.length === 0}
      <div class="govuk-inset-text">
        No methods loaded. Press <strong>Load sample methods</strong> to see three example agents
        compared on one form, or import a <code>RunLog</code> JSON exported from the
        <a class="govuk-link" href="/log">run log</a> page.
      </div>
    {:else if activeGroup}
      <!-- Which form is being compared -->
      {#if formGroups.length > 1}
        <div class="govuk-form-group cmp-formpick">
          <label class="govuk-label govuk-label--s" for="formpick">Form being compared</label>
          <div id="formpick-hint" class="govuk-hint">
            Each form is a separate comparison. Only methods that ran the selected form are shown below.
          </div>
          <select
            class="govuk-select"
            id="formpick"
            aria-describedby="formpick-hint"
            value={activeGroup.formId}
            onchange={(e) => (activeFormId = (e.currentTarget as HTMLSelectElement).value)}
          >
            {#each formGroups as group (group.formId)}
              <option value={group.formId}>
                {group.formName ?? group.formId}, {group.methods.length} method{group.methods.length === 1 ? "" : "s"}
              </option>
            {/each}
          </select>
        </div>
      {:else}
        <p class="govuk-body">
          Comparing <strong>{activeGroup.methods.length}</strong> method{activeGroup.methods.length === 1 ? "" : "s"}
          that ran <strong>{activeGroup.formName ?? activeGroup.formId}</strong>.
        </p>
      {/if}

      {#if activeGroup.methods.length < 2}
        <div class="govuk-inset-text">
          <p class="govuk-body">
            Only one method ran <strong>{activeGroup.formName ?? activeGroup.formId}</strong>, so
            there's nothing to compare yet. Import another method's log for this form, or generate
            synthetic comparators from this run to see how it stacks up against a verbose and an
            over-eager method.
          </p>
          <button
            type="button"
            class="govuk-button govuk-button--secondary cmp-gen"
            onclick={() => generateComparators(activeGroup.methods[0].log)}
          >
            Generate verbose + aggressive comparators
          </button>
        </div>
      {/if}

      <!-- The methods -->
      <h2 class="govuk-heading-m">The methods</h2>
      <div class="cmp-methods">
        {#each orderedMethods as method (method.id)}
          <div class={`cmp-method ${isReference(method.id) ? "cmp-method--ref" : ""}`}>
            <div class="cmp-method__head">
              <h3 class="govuk-heading-s cmp-method__name">{method.label}</h3>
              {#if isReference(method.id)}
                <strong class="govuk-tag govuk-tag--blue">baseline</strong>
              {/if}
              <button
                type="button"
                class="cmp-method__remove"
                onclick={() => removeMethod(method.id)}
                aria-label={`Remove ${method.label}`}
              >
                Remove
              </button>
            </div>
            <p class="govuk-body-s cmp-method__meta">
              {method.log.form.name ?? method.log.form.id} · method: {method.log.method} · model: {method.log.model}
            </p>
            <p class="govuk-body-s">{method.log.description ?? "No description provided."}</p>
          </div>
        {/each}
      </div>

      {#if activeGroup.methods.length >= 2 && !activeGroup.methods.some((m) => m.log.method.includes("(synthetic)"))}
        <p class="govuk-body">
          <button
            type="button"
            class="govuk-button govuk-button--secondary cmp-gen"
            onclick={() => generateComparators(orderedMethods[0].log)}
          >
            Add synthetic verbose + aggressive comparators
          </button>
        </p>
      {/if}

      {#if activeGroup.methods.length >= 2 && scorecard}
        <!-- At a glance -->
        <h2 class="govuk-heading-m">At a glance</h2>
        <div class="govuk-form-group cmp-measure">
          <label class="govuk-label govuk-label--s" for="measure">Measure</label>
          <select
            class="govuk-select"
            id="measure"
            value={glanceMetric}
            onchange={(e) => (glanceMetric = (e.currentTarget as HTMLSelectElement).value as typeof glanceMetric)}
          >
            <option value="tokens">Total tokens</option>
            <option value="turns">Conversation turns</option>
            <option value="questions">Questions asked of the human</option>
            <option value="filled">Filled by the agent</option>
            <option value="fill">Left for a human to fill in</option>
          </select>
        </div>
        <div class="cmp-bars">
          {#each glance.rows as row (row.id)}
            <div class="cmp-bar">
              <div class="govuk-body-s cmp-bar__label">{row.label}</div>
              <div class="cmp-bar__track">
                <div class="cmp-bar__fill" style={`width:${(row.value / glance.max) * 100}%`}></div>
              </div>
              <div class="govuk-body-s cmp-bar__value">{glanceOptions[glanceMetric].format(row.value)}</div>
            </div>
          {/each}
        </div>
        <p class="govuk-hint">{glanceOptions[glanceMetric].explain} Bar length is relative to the largest.</p>

        <!-- Scorecard -->
        <h2 class="govuk-heading-m">Scorecard</h2>
        <p class="govuk-hint">
          A ✓ marks the best value where lower is better. Cost is only ranked among methods that used
          an LLM.
        </p>
        <div class="cmp-scroll">
          <table class="govuk-table">
            <thead class="govuk-table__head">
              <tr class="govuk-table__row">
                <th class="govuk-table__header" scope="col">Metric</th>
                {#each orderedMethods as method (method.id)}
                  <th class="govuk-table__header govuk-table__header--numeric" scope="col">
                    {method.label}
                    {#if isReference(method.id)}<br /><span class="cmp-th-note">baseline</span>{/if}
                  </th>
                {/each}
              </tr>
            </thead>
            <tbody class="govuk-table__body">
              {#each scorecardGroups as group (group.name)}
                <tr class="govuk-table__row cmp-rowgroup">
                  <th class="govuk-table__header" colspan={orderedMethods.length + 1} scope="colgroup">{group.name}</th>
                </tr>
                {#each group.rows as srow (srow.label)}
                  <tr class="govuk-table__row">
                    <td class="govuk-table__cell">{srow.label}</td>
                    {#each srow.display as value, i (i)}
                      <td
                        class={`govuk-table__cell govuk-table__cell--numeric ${srow.bestIndexes.includes(i) ? "cmp-best" : ""} ${srow.agenticOnly && !scorecard.agenticFlags[i] ? "cmp-muted" : ""}`}
                      >
                        {value}{#if srow.bestIndexes.includes(i)}&nbsp;✓{/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              {/each}
            </tbody>
          </table>
        </div>

        <!-- Divergence -->
        <h2 class="govuk-heading-m">What each method did, question by question</h2>
        {#if divergence}
          <div class="govuk-form-group cmp-refpick">
            <label class="govuk-label govuk-label--s" for="refpick">Baseline to compare against</label>
            <select
              class="govuk-select"
              id="refpick"
              value={activeReference}
              onchange={(e) => (referenceId = (e.currentTarget as HTMLSelectElement).value)}
            >
              {#each activeGroup.methods as method (method.id)}
                <option value={method.id}>{method.label}</option>
              {/each}
            </select>
          </div>
          <p class="govuk-hint">
            Each candidate is marked <strong>same</strong> or <strong>differs</strong> versus the
            baseline (<strong>{divergence.referenceLabel}</strong>). “⚠ unverified” means the value was
            filled but a human still needs to confirm it.
          </p>
          <div class="cmp-scroll">
            <table class="govuk-table">
              <thead class="govuk-table__head">
                <tr class="govuk-table__row">
                  <th class="govuk-table__header" scope="col">Question</th>
                  <th class="govuk-table__header" scope="col">
                    {divergence.referenceLabel}<br /><span class="cmp-th-note">baseline</span>
                  </th>
                  {#each divergence.candidateColumns as col (col.id)}
                    <th class="govuk-table__header" scope="col">{col.label}</th>
                  {/each}
                </tr>
              </thead>
              <tbody class="govuk-table__body">
                {#each divergence.rows as drow (drow.field)}
                  <tr class="govuk-table__row">
                    <td class="govuk-table__cell">{drow.questionText}</td>
                    <td class="govuk-table__cell" title={drow.referenceDetail ?? ""}>
                      <strong class={`govuk-tag ${actionTag(drow.reference)}`}>{actionLabel(drow.reference)}</strong>
                      {#if drow.referenceNeedsHuman}<span class="cmp-unverified">⚠ unverified</span>{/if}
                    </td>
                    {#each drow.candidates as cand (cand.id)}
                      <td class={`govuk-table__cell ${cand.differs ? "cmp-differs" : ""}`} title={cand.detail ?? ""}>
                        <strong class={`govuk-tag ${actionTag(cand.action)}`}>{actionLabel(cand.action)}</strong>
                        {#if cand.needsHuman}<span class="cmp-unverified">⚠ unverified</span>{/if}
                        <span class={`cmp-flag ${cand.differs ? "cmp-flag--differs" : "cmp-flag--same"}`}>
                          {cand.differs ? "differs" : "same"}
                        </span>
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <!-- Turn-by-turn detail -->
          <h2 class="govuk-heading-m">Turn-by-turn</h2>
          <p class="govuk-hint">How each method's conversation actually went, turn by turn.</p>
          {#each orderedMethods as method (method.id)}
            <details class="govuk-details">
              <summary class="govuk-details__summary">
                <span class="govuk-details__summary-text">{method.label}, {method.log.criteria.interaction.length} turn{method.log.criteria.interaction.length === 1 ? "" : "s"}</span>
              </summary>
              <div class="govuk-details__text">
                <ol class="cmp-turns">
                  {#each method.log.criteria.interaction as turn (turn.turn)}
                    <li class="cmp-turn">
                      <span class="cmp-turn__tag">Turn {turn.turn}</span>
                      <span class="cmp-turn__body">
                        <span class="govuk-body-s cmp-turn__line"><strong>Citizen:</strong> {turn.user}</span>
                        <span class="govuk-body-s cmp-turn__line">
                          <strong>{turn.awaitingInput ? "Agent asks:" : "Agent:"}</strong> {turn.agent}
                        </span>
                        {#if turn.newFields.length > 0}
                          <span class="govuk-body-s cmp-turn__fields">filled this turn: {turn.newFields.join(", ")}</span>
                        {/if}
                      </span>
                    </li>
                  {/each}
                </ol>
              </div>
            </details>
          {/each}
        {/if}
      {/if}

      <!-- Methods on other forms -->
      {#if otherGroups.length > 0}
        <div class="govuk-inset-text">
          Also loaded, but on other forms (not comparable with the above):
          <ul class="govuk-list govuk-list--bullet cmp-other">
            {#each otherGroups as group (group.formId)}
              <li>
                <strong>{group.formName ?? group.formId}</strong>: {group.methods.map((m) => m.label).join(", ")}
                {#if formGroups.length > 1}(select it in “Form being compared” to view){/if}
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    {/if}
  </main>
</div>

<style>
  /* GDS applies its font only to .govuk-* classes; setting it here means every
     bespoke element inherits it too, instead of falling back to a serif. */
  .cmp {
    font-family: "GDS Transport", arial, sans-serif;
  }

  .cmp-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .cmp-controls :global(.govuk-button) {
    margin-bottom: 0;
  }

  .cmp-import {
    position: relative;
    overflow: hidden;
    cursor: pointer;
  }

  .cmp-gen {
    margin-bottom: 0;
  }

  /* Blue accent so the "already loaded" notice is not mistaken for body text. */
  .cmp-notice {
    border-color: #1d70b8;
  }

  .cmp-import__input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .cmp-formpick,
  .cmp-measure,
  .cmp-refpick {
    max-width: 30rem;
  }

  .cmp-methods {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .cmp-method {
    border: 1px solid #b1b4b6;
    border-top: 4px solid #b1b4b6;
    padding: 0.75rem 1rem 1rem;
  }

  .cmp-method--ref {
    border-top-color: #1d70b8;
    background: #f0f6fb;
  }

  .cmp-method__head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .cmp-method__name {
    margin: 0;
  }

  .cmp-method__remove {
    margin-left: auto;
    border: 0;
    background: transparent;
    color: #1d70b8;
    text-decoration: underline;
    cursor: pointer;
    font: inherit;
    padding: 0;
  }

  .cmp-method__meta {
    margin: 0 0 0.5rem;
    color: #505a5f;
  }

  .cmp-bars {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .cmp-bar {
    display: grid;
    grid-template-columns: 14rem 1fr 6rem;
    gap: 0.75rem;
    align-items: center;
  }

  .cmp-bar__label {
    margin: 0;
    font-weight: 700;
  }

  .cmp-bar__track {
    background: #f3f2f1;
    border: 1px solid #dcdee0;
    height: 1.5rem;
  }

  .cmp-bar__fill {
    height: 100%;
    background: #1d70b8;
    min-width: 2px;
  }

  .cmp-bar__value {
    margin: 0;
    text-align: right;
  }

  .cmp-scroll {
    overflow-x: auto;
  }

  .cmp-rowgroup th {
    background: #f3f2f1;
  }

  .cmp-best {
    font-weight: 700;
    color: #00703c;
  }

  .cmp-muted {
    color: #768692;
    font-style: italic;
  }

  .cmp-th-note {
    font-weight: 400;
    font-size: 0.75rem;
    color: #1d70b8;
    text-transform: uppercase;
  }

  .cmp-differs {
    background: #fff7bf;
  }

  .cmp-flag {
    display: inline-block;
    margin-left: 0.35rem;
    font-size: 0.75rem;
    text-transform: uppercase;
  }

  .cmp-flag--differs {
    color: #d4351c;
    font-weight: 700;
  }

  .cmp-flag--same {
    color: #768692;
  }

  .cmp-unverified {
    display: inline-block;
    margin-left: 0.35rem;
    font-size: 0.75rem;
    color: #b58840;
  }

  .cmp-turns {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .cmp-turn {
    display: grid;
    grid-template-columns: 4.5rem 1fr;
    gap: 0.75rem;
  }

  .cmp-turn__tag {
    font-weight: 700;
    color: #1d70b8;
  }

  .cmp-turn__body {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .cmp-turn__line {
    margin: 0;
  }

  .cmp-turn__fields {
    margin: 0;
    color: #505a5f;
  }

  .cmp-other {
    margin-bottom: 0;
  }

  @media (max-width: 40rem) {
    .cmp-bar {
      grid-template-columns: 1fr;
      gap: 0.15rem;
    }

    .cmp-bar__value {
      text-align: left;
    }
  }
</style>
