<script lang="ts">
  import { onMount } from "svelte";
  import { traceStore } from "$lib/stores/trace.svelte";
  import {
    IMPLEMENTATION_AGGRESSIVE_SYNTHETIC,
    IMPLEMENTATION_VERBOSE_SYNTHETIC,
    parseCommonTrace,
    type CommonTrace,
    type TraceEvent,
  } from "$lib/common-trace";
  import { SAMPLE_METHODS } from "$lib/fixtures";
  import { deriveComparators } from "$lib/variants";
  import {
    buildDivergence,
    buildScorecard,
    groupByJourney,
    methodMetrics,
    type Method,
    type MethodMetrics,
  } from "$lib/compare-metrics";
  import { eventDetail, eventLabel, eventTag, formatValues, groupEventsByInteraction, implementationLabel, statusTag } from "$lib/trace-display";

  let methods = $state<Method[]>([]);
  let importError = $state<string | null>(null);
  // Neutral feedback (not an error) — e.g. an imported file was already loaded.
  let importNotice = $state<string | null>(null);
  let activeJourneyId = $state<string | null>(null);
  let glanceMetric = $state<"proposed" | "submitted" | "available" | "outstanding" | "failures">("proposed");

  onMount(() => {
    if (traceStore.trace) addMethod(traceStore.trace);
  });

  // Whether each accordion section is open. This app has no bundled GOV.UK
  // Frontend JavaScript, so the accordion's open/closed behaviour (normally
  // driven by that script) is reproduced here instead; the real govuk-accordion
  // markup and CSS classes still do the rendering. All three start open.
  type AccordionSection = "glance" | "scorecard" | "divergence";
  let sectionsOpen = $state<Record<AccordionSection, boolean>>({
    glance: true,
    scorecard: true,
    divergence: true,
  });

  function toggleSection(section: AccordionSection) {
    sectionsOpen[section] = !sectionsOpen[section];
  }

  const allSectionsOpen = $derived(Object.values(sectionsOpen).every(Boolean));

  function toggleAllSections() {
    const next = !allSectionsOpen;
    sectionsOpen = { glance: next, scorecard: next, divergence: next };
  }

  // A globally-unique key for a method, based on the run id every common
  // trace already carries.
  function uniqueId(trace: CommonTrace): string {
    const base = trace.run.id;
    const existing = new Set(methods.map((m) => m.id));
    if (!existing.has(base)) return base;
    let n = 2;
    while (existing.has(`${base}#${n}`)) n += 1;
    return `${base}#${n}`;
  }

  // A display label that is unique WITHIN its journey group. Labels only
  // need to be unique within one journey, because only one journey's methods
  // are shown at a time.
  function makeLabel(trace: CommonTrace): string {
    const base = implementationLabel(trace.run.implementation);
    const sameJourney = methods.filter((m) => m.trace.run.journey_id === trace.run.journey_id);
    const existing = new Set(sameJourney.map((m) => m.label));
    if (!existing.has(base)) return base;
    let n = 2;
    while (existing.has(`${base} (${n})`)) n += 1;
    return `${base} (${n})`;
  }

  // Adds a trace unless the same run is already loaded (by run id). Returns
  // true if it was added, false if it was skipped as a duplicate, so callers
  // can tell the user rather than fail silently.
  function addMethod(trace: CommonTrace): boolean {
    if (methods.some((m) => m.trace.run.id === trace.run.id)) return false;
    methods = [...methods, { id: uniqueId(trace), label: makeLabel(trace), trace }];
    return true;
  }

  function loadSamples() {
    for (const trace of SAMPLE_METHODS) addMethod(trace);
  }

  // Builds revision-heavy + single-pass comparators from a real trace, on
  // the same journey, so a single loaded method has something to compare
  // against.
  function generateComparators(base: Method) {
    const generated = deriveComparators(base.trace, {
      revisionHeavy: crypto.randomUUID(),
      singlePass: crypto.randomUUID(),
    });
    for (const trace of generated) addMethod(trace);
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
        const trace = parseCommonTrace(JSON.parse(await file.text()));
        if (!addMethod(trace)) skipped.push(file.name);
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

  // Methods can only be compared within one journey. Group them, then work
  // inside the active group (default: the largest).
  const journeyGroups = $derived(groupByJourney(methods));
  const activeGroup = $derived(
    journeyGroups.find((g) => g.journeyId === activeJourneyId) ?? journeyGroups[0] ?? null,
  );
  const otherGroups = $derived(journeyGroups.filter((g) => g !== activeGroup));

  // The active methods, in the order they were loaded. The reference
  // (baseline for the scorecard and divergence) is simply whichever one is
  // first; there is no separate picker for it.
  const orderedMethods = $derived<Method[]>(activeGroup?.methods ?? []);
  const activeReference = $derived(orderedMethods[0]?.id ?? null);

  const scorecard = $derived(orderedMethods.length > 0 ? buildScorecard(orderedMethods) : null);
  const divergence = $derived(buildDivergence(orderedMethods, activeReference));

  function isReference(id: string): boolean {
    return id === activeReference;
  }

  // Whether a generated comparator is already in the active group, so the
  // "generate" button does not offer to pile up duplicates.
  const hasSyntheticComparator = $derived(
    (activeGroup?.methods ?? []).some(
      (m) =>
        m.trace.run.implementation === IMPLEMENTATION_VERBOSE_SYNTHETIC ||
        m.trace.run.implementation === IMPLEMENTATION_AGGRESSIVE_SYNTHETIC,
    ),
  );

  // "At a glance" bar chart data for the chosen headline metric. The common
  // trace carries no timing or token cost, so these are event counts.
  const glanceOptions = {
    proposed: {
      label: "Values proposed",
      explain: "How many times the method proposed a value, across every interaction, including revisions.",
      pick: (m: MethodMetrics) => m.valuesProposed,
    },
    submitted: {
      label: "Values submitted",
      explain: "How many interactions the method submitted a final value for.",
      pick: (m: MethodMetrics) => m.valuesSubmitted,
    },
    available: {
      label: "Interactions made available",
      explain: "How many distinct interactions the method's journey reached.",
      pick: (m: MethodMetrics) => m.interactionsAvailable,
    },
    outstanding: {
      label: "Left without a submitted value",
      explain: "Interactions that became available but never got a final submitted value, such as an upload left for a human.",
      pick: (m: MethodMetrics) => m.interactionsAvailable - m.valuesSubmitted,
    },
    failures: {
      label: "Assistance failures",
      explain: "How many turns the agent call itself failed to produce a usable result.",
      pick: (m: MethodMetrics) => m.assistanceFailures,
    },
  } as const;

  const glance = $derived.by(() => {
    const rows = orderedMethods.map((m) => {
      const metrics = methodMetrics(m.trace);
      return { id: m.id, label: m.label, value: glanceOptions[glanceMetric].pick(metrics) };
    });
    const max = Math.max(1, ...rows.map((r) => r.value));
    return { rows, max };
  });

  // The events belonging to one method, for the "event by event" breakdown,
  // grouped by interaction rather than left in raw chronological order so
  // every event for one question sits together. The run-level
  // journey_finished event is summarised separately in the method's card
  // above, so it is left out here.
  function methodEvents(method: Method): TraceEvent[] {
    return groupEventsByInteraction(method.trace.events.filter((event) => event.type !== "journey_finished"));
  }
</script>

<div class="govuk-width-container page-fill cmp">
  <main class="govuk-main-wrapper" id="main-content">
    <a class="govuk-back-link" href="/log">Back to the run log</a>

    <h1 class="govuk-heading-l">Compare methods</h1>
    <p class="govuk-body">
      Put different form-filling methods side by side, using their common traces. Methods can only be
      compared when they ran the <strong>same journey</strong> (same questions, same branching), so the
      page compares one journey at a time. Load the sample methods to see how it works, or import common
      traces of your own.
    </p>

    <div class="cmp-controls">
      <button type="button" class="govuk-button govuk-button--secondary" onclick={loadSamples}>
        Load sample methods
      </button>
      <label class="govuk-button govuk-button--secondary cmp-import">
        Import trace(s)…
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
        No methods loaded. Press <strong>Load sample methods</strong> to see three example methods
        compared on one journey, or import a common trace JSON file exported from the
        <a class="govuk-link" href="/log">run log</a> page.
      </div>
    {:else if activeGroup}
      <!-- Which journey is being compared -->
      {#if journeyGroups.length > 1}
        <div class="govuk-form-group cmp-journeypick">
          <label class="govuk-label govuk-label--s" for="journeypick">Journey being compared</label>
          <div id="journeypick-hint" class="govuk-hint">
            Each journey is a separate comparison. Only methods that ran the selected journey are shown below.
          </div>
          <select
            class="govuk-select"
            id="journeypick"
            aria-describedby="journeypick-hint"
            value={activeGroup.journeyId}
            onchange={(e) => (activeJourneyId = (e.currentTarget as HTMLSelectElement).value)}
          >
            {#each journeyGroups as group (group.journeyId)}
              <option value={group.journeyId}>
                {group.journeyName ?? group.journeyId}, {group.methods.length} method{group.methods.length === 1 ? "" : "s"}
              </option>
            {/each}
          </select>
        </div>
      {:else}
        <p class="govuk-body">
          Comparing <strong>{activeGroup.methods.length}</strong> method{activeGroup.methods.length === 1 ? "" : "s"}
          that ran <strong>{activeGroup.journeyName ?? activeGroup.journeyId}</strong>.
        </p>
      {/if}

      {#if activeGroup.methods.length < 2}
        <div class="govuk-inset-text">
          <p class="govuk-body">
            Only one method ran <strong>{activeGroup.journeyName ?? activeGroup.journeyId}</strong>, so
            there's nothing to compare yet. Import another method's trace for this journey, or generate
            synthetic comparators from this run to see how it stacks up against a revision-heavy and a
            single-pass method.
          </p>
          <button
            type="button"
            class="govuk-button govuk-button--secondary cmp-gen"
            onclick={() => generateComparators(activeGroup.methods[0])}
          >
            Generate revision-heavy + single-pass comparators
          </button>
        </div>
      {/if}

      <!-- The methods -->
      <h2 class="govuk-heading-m">The methods</h2>
      <div class="cmp-methods">
        {#each orderedMethods as method (method.id)}
          <div class="govuk-summary-card">
            <div class="govuk-summary-card__title-wrapper">
              <h3 class="govuk-summary-card__title">{method.label}</h3>
              <ul class="govuk-summary-card__actions">
                {#if isReference(method.id)}
                  <li class="govuk-summary-card__action">
                    <strong class="govuk-tag govuk-tag--blue">baseline</strong>
                  </li>
                {/if}
                <li class="govuk-summary-card__action">
                  <button type="button" class="cmp-remove" onclick={() => removeMethod(method.id)}>
                    Remove<span class="govuk-visually-hidden"> {method.label}</span>
                  </button>
                </li>
              </ul>
            </div>
            <div class="govuk-summary-card__content">
              <p class="govuk-body-s cmp-method-impl"><code>{method.trace.run.implementation}</code></p>
              <p class="govuk-body-s">
                <strong class={`govuk-tag ${statusTag(method.trace.run.status)}`}>{method.trace.run.status}</strong>
              </p>
            </div>
          </div>
        {/each}
      </div>

      {#if activeGroup.methods.length >= 2 && !hasSyntheticComparator}
        <p class="govuk-body">
          <button
            type="button"
            class="govuk-button govuk-button--secondary cmp-gen"
            onclick={() => generateComparators(orderedMethods[0])}
          >
            Add revision-heavy + single-pass comparators
          </button>
        </p>
      {/if}

      {#if activeGroup.methods.length >= 2 && scorecard}
        <!-- This app has no bundled GOV.UK Frontend JavaScript, so the
             open/closed behaviour that script would normally drive is
             reproduced here in Svelte; govuk-frontend-supported switches on
             the same CSS the real script relies on. -->
        <div class="govuk-accordion govuk-frontend-supported">
          <button type="button" class="govuk-accordion__show-all" aria-expanded={allSectionsOpen} onclick={toggleAllSections}>
            <span class={`govuk-accordion-nav__chevron ${allSectionsOpen ? "" : "govuk-accordion-nav__chevron--down"}`}></span>
            <span class="govuk-accordion__show-all-text">{allSectionsOpen ? "Hide all sections" : "Show all sections"}</span>
          </button>

          <!-- At a glance -->
          <div class={`govuk-accordion__section ${sectionsOpen.glance ? "govuk-accordion__section--expanded" : ""}`}>
            <div class="govuk-accordion__section-header">
              <h2 class="govuk-accordion__section-heading">
                <button
                  type="button"
                  class="govuk-accordion__section-button"
                  aria-expanded={sectionsOpen.glance}
                  aria-controls="cmp-section-glance"
                  onclick={() => toggleSection("glance")}
                >
                  <span class="govuk-accordion__section-heading-text">
                    <span class="govuk-accordion__section-heading-text-focus">At a glance</span>
                  </span>
                  <span class="govuk-accordion__section-toggle" data-nosnippet>
                    <span class="govuk-accordion__section-toggle-focus">
                      <span class={`govuk-accordion-nav__chevron ${sectionsOpen.glance ? "" : "govuk-accordion-nav__chevron--down"}`}></span>
                      <span class="govuk-accordion__section-toggle-text">{sectionsOpen.glance ? "Hide" : "Show"}</span>
                    </span>
                  </span>
                </button>
              </h2>
            </div>
            <div id="cmp-section-glance" class="govuk-accordion__section-content">
              <div class="govuk-form-group cmp-measure">
                <label class="govuk-label govuk-label--s" for="measure">Measure</label>
                <select
                  class="govuk-select"
                  id="measure"
                  value={glanceMetric}
                  onchange={(e) => (glanceMetric = (e.currentTarget as HTMLSelectElement).value as typeof glanceMetric)}
                >
                  {#each Object.entries(glanceOptions) as [key, option] (key)}
                    <option value={key}>{option.label}</option>
                  {/each}
                </select>
              </div>
              <div class="cmp-bars">
                {#each glance.rows as row (row.id)}
                  <div class="cmp-bar">
                    <div class="govuk-body-s cmp-bar__label">{row.label}</div>
                    <div class="cmp-bar__track">
                      <div class="cmp-bar__fill" style={`width:${(row.value / glance.max) * 100}%`}></div>
                    </div>
                    <div class="govuk-body-s cmp-bar__value">{row.value}</div>
                  </div>
                {/each}
              </div>
              <p class="govuk-hint">{glanceOptions[glanceMetric].explain} Bar length is relative to the largest.</p>
            </div>
          </div>

          <!-- Scorecard -->
          <div class={`govuk-accordion__section ${sectionsOpen.scorecard ? "govuk-accordion__section--expanded" : ""}`}>
            <div class="govuk-accordion__section-header">
              <h2 class="govuk-accordion__section-heading">
                <button
                  type="button"
                  class="govuk-accordion__section-button"
                  aria-expanded={sectionsOpen.scorecard}
                  aria-controls="cmp-section-scorecard"
                  onclick={() => toggleSection("scorecard")}
                >
                  <span class="govuk-accordion__section-heading-text">
                    <span class="govuk-accordion__section-heading-text-focus">Scorecard</span>
                  </span>
                  <span class="govuk-accordion__section-toggle" data-nosnippet>
                    <span class="govuk-accordion__section-toggle-focus">
                      <span class={`govuk-accordion-nav__chevron ${sectionsOpen.scorecard ? "" : "govuk-accordion-nav__chevron--down"}`}></span>
                      <span class="govuk-accordion__section-toggle-text">{sectionsOpen.scorecard ? "Hide" : "Show"}</span>
                    </span>
                  </span>
                </button>
              </h2>
            </div>
            <div id="cmp-section-scorecard" class="govuk-accordion__section-content">
              <p class="govuk-hint">A ✓ marks the best value where lower is better.</p>
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
                    {#each scorecard.rows as srow (srow.label)}
                      <tr class="govuk-table__row">
                        <td class="govuk-table__cell">{srow.label}</td>
                        {#each srow.display as value, i (i)}
                          <td class={`govuk-table__cell govuk-table__cell--numeric ${srow.bestIndexes.includes(i) ? "cmp-best" : ""}`}>
                            {value}{#if srow.bestIndexes.includes(i)}&nbsp;✓{/if}
                          </td>
                        {/each}
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Divergence -->
          <div class={`govuk-accordion__section ${sectionsOpen.divergence ? "govuk-accordion__section--expanded" : ""}`}>
            <div class="govuk-accordion__section-header">
              <h2 class="govuk-accordion__section-heading">
                <button
                  type="button"
                  class="govuk-accordion__section-button"
                  aria-expanded={sectionsOpen.divergence}
                  aria-controls="cmp-section-divergence"
                  onclick={() => toggleSection("divergence")}
                >
                  <span class="govuk-accordion__section-heading-text">
                    <span class="govuk-accordion__section-heading-text-focus">What information was submitted</span>
                  </span>
                  <span class="govuk-accordion__section-toggle" data-nosnippet>
                    <span class="govuk-accordion__section-toggle-focus">
                      <span class={`govuk-accordion-nav__chevron ${sectionsOpen.divergence ? "" : "govuk-accordion-nav__chevron--down"}`}></span>
                      <span class="govuk-accordion__section-toggle-text">{sectionsOpen.divergence ? "Hide" : "Show"}</span>
                    </span>
                  </span>
                </button>
              </h2>
            </div>
            <div id="cmp-section-divergence" class="govuk-accordion__section-content">
              {#if divergence}
                <p class="govuk-hint">
                  Compared against the baseline, <strong>{divergence.referenceLabel}</strong> (the first
                  method loaded). A cell that differs from the baseline is highlighted.
                </p>
                <div class="cmp-scroll">
                  <table class="govuk-table cmp-divergence">
                    <thead class="govuk-table__head">
                      <tr class="govuk-table__row">
                        <th class="govuk-table__header" scope="col">Interaction</th>
                        <th class="govuk-table__header" scope="col">
                          {divergence.referenceLabel}<br /><span class="cmp-th-note">baseline</span>
                        </th>
                        {#each divergence.candidateColumns as col (col.id)}
                          <th class="govuk-table__header" scope="col">{col.label}</th>
                        {/each}
                      </tr>
                    </thead>
                    <tbody class="govuk-table__body">
                      {#each divergence.rows as drow (drow.interactionId)}
                        <tr class="govuk-table__row">
                          <td class="govuk-table__cell"><code>{drow.interactionId}</code></td>
                          <td class="govuk-table__cell">
                            {#if !drow.reference.reached}
                              <span class="govuk-hint">not reached</span>
                            {:else if !drow.reference.values}
                              <strong class="govuk-tag govuk-tag--grey">no value yet</strong>
                            {:else}
                              <strong class={`govuk-tag ${drow.reference.source === "submitted" ? "govuk-tag--green" : "govuk-tag--teal"}`}>
                                {drow.reference.source}
                              </strong>
                              <div class="govuk-body-s cmp-value">{formatValues(drow.reference.values, drow.interactionId)}</div>
                            {/if}
                          </td>
                          {#each drow.candidates as cand (cand.id)}
                            <td class={`govuk-table__cell ${cand.differs ? "cmp-differs" : ""}`}>
                              {#if !cand.reached}
                                <span class="govuk-hint">not reached</span>
                              {:else if !cand.values}
                                <strong class="govuk-tag govuk-tag--grey">no value yet</strong>
                              {:else}
                                <strong class={`govuk-tag ${cand.source === "submitted" ? "govuk-tag--green" : "govuk-tag--teal"}`}>
                                  {cand.source}
                                </strong>
                                <div class="govuk-body-s cmp-value">{formatValues(cand.values, drow.interactionId)}</div>
                              {/if}
                            </td>
                          {/each}
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {/if}
            </div>
          </div>
        </div>

        <!-- Event-by-event detail -->
        {#if divergence}
          <h2 class="govuk-heading-m">Event by event</h2>
          <p class="govuk-hint">Each method's own common trace events, in interaction order.</p>
          {#each orderedMethods as method (method.id)}
            <details class="govuk-details">
              <summary class="govuk-details__summary">
                <span class="govuk-details__summary-text">{method.label}, {methodEvents(method).length} event{methodEvents(method).length === 1 ? "" : "s"}</span>
              </summary>
              <div class="govuk-details__text">
                <table class="govuk-table">
                  <thead class="govuk-table__head">
                    <tr class="govuk-table__row">
                      <th class="govuk-table__header">Event</th>
                      <th class="govuk-table__header">Interaction</th>
                      <th class="govuk-table__header">Detail</th>
                    </tr>
                  </thead>
                  <tbody class="govuk-table__body">
                    {#each methodEvents(method) as event, i (i)}
                      <tr class="govuk-table__row">
                        <td class="govuk-table__cell">
                          <strong class={`govuk-tag ${eventTag(event.type)}`}>{eventLabel(event.type)}</strong>
                        </td>
                        <td class="govuk-table__cell">
                          <code>{"interaction_id" in event ? (event.interaction_id ?? "-") : "-"}</code>
                        </td>
                        <td class="govuk-table__cell">{eventDetail(event)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </details>
          {/each}
        {/if}
      {/if}

      <!-- Methods on other journeys -->
      {#if otherGroups.length > 0}
        <div class="govuk-inset-text">
          Also loaded, but on other journeys (not comparable with the above):
          <ul class="govuk-list govuk-list--bullet cmp-other">
            {#each otherGroups as group (group.journeyId)}
              <li>
                <strong>{group.journeyName ?? group.journeyId}</strong>: {group.methods.map((m) => m.label).join(", ")}
                {#if journeyGroups.length > 1}(select it in “Journey being compared” to view){/if}
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

  /* A code element has no bundled GDS typeface to fall back to on its own, so
     without this it renders in the browser's own default monospace font
     instead of matching the rest of the page. */
  .cmp :global(code) {
    font-family: inherit;
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

  .cmp-journeypick,
  .cmp-measure {
    max-width: 30rem;
  }

  .cmp-methods {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 1rem;
    /* govuk-heading-m has no top margin of its own, so without this the
       heading straight after this grid sits flush against the cards. */
    margin-bottom: 30px;
  }

  /* GDS gives every govuk-summary-card the same bottom margin, which looks
     uneven inside a grid where cards already have row gaps. */
  .cmp-methods :global(.govuk-summary-card) {
    margin-bottom: 0;
  }

  /* A govuk-summary-list splits into a fixed-percentage two column layout,
     which assumes a wider container than one card in a three-up grid gives
     it; that squeezed "Implementation" into an unreadable wrap. A plain line
     does not have that assumption. Breaking on any character, not just
     spaces, stops a long implementation identifier overflowing the card. */
  .cmp-method-impl {
    overflow-wrap: anywhere;
  }

  /* GDS's own :link/:visited colouring only applies to real anchors, and
     this needs a JS action rather than a navigation, so the one thing worth
     a custom rule is the colour a real govuk-link would have had. */
  .cmp-remove {
    border: 0;
    background: transparent;
    color: #1d70b8;
    text-decoration: underline;
    cursor: pointer;
    font: inherit;
    /* govuk-summary-card__actions sets font-weight: 700 for its whole action
       list, meant for adjacent text like "baseline"; a link should not be bold. */
    font-weight: 400;
    padding: 0;
  }

  .cmp-remove:hover {
    color: #003078;
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

  .cmp-best {
    font-weight: 700;
    color: #00703c;
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

  /* Without a minimum, a divergence table with several candidate columns
     squeezes each one down to little more than the tag's own width. */
  .cmp-divergence :global(th),
  .cmp-divergence :global(td) {
    min-width: 10rem;
  }

  /* A govuk-tag has no bottom margin of its own, so the value line under it
     would otherwise sit flush against it. */
  .cmp-value {
    margin-top: 0.35rem;
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
