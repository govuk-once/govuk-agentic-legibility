<script lang="ts">
  import { onMount } from 'svelte';
  import SchemaForm from '$lib/components/SchemaForm.svelte';
  import type { Interaction } from '$lib/types';

  type ListedForm = { id: string; name: string };
  type Run = { run_id: string; form_id: string; status: string; terminal: boolean;
    interaction: Interaction | null; answers: Record<string, unknown> };
  const API = 'http://127.0.0.1:8002';
  let forms: ListedForm[] = [];
  let selectedId = '';
  let run: Run | null = null;
  let error = '';
  let busy = false;

  onMount(async () => {
    try {
      const response = await fetch(`${API}/api/forms`);
      if (!response.ok) throw new Error(await response.text());
      forms = await response.json();
      const requested = new URLSearchParams(window.location.search).get('id');
      selectedId = requested && forms.some((form) => form.id === requested) ? requested : forms[0]?.id || '';
    } catch (e) { error = String(e); }
  });

  async function start(): Promise<void> {
    if (!selectedId) return;
    busy = true; error = ''; run = null;
    try {
      const response = await fetch(`${API}/api/forms/${selectedId}/runs`, { method: 'POST' });
      if (!response.ok) throw new Error(await response.text());
      run = await response.json();
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }

  async function submit(values: Record<string, unknown>): Promise<void> {
    if (!run) return;
    busy = true; error = '';
    try {
      const response = await fetch(`${API}/api/forms/runs/${run.run_id}/answers`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: values.answer ?? null })
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || response.statusText);
      }
      run = await response.json();
    } catch (e) { error = String(e); }
    finally { busy = false; }
  }

  $: presentation = run?.interaction?.content?.forms as Record<string, unknown> | undefined;
</script>
<svelte:head><title>GOV.UK Forms SFSM preview</title></svelte:head>
<main>
  <a href="/">Back to journey prototype</a>
  <p class="tag">Local development preview · No submission</p>
  <h1>GOV.UK Forms journeys</h1>
  <p>This preview executes the compiled SFSM transitions. Use synthetic information only; answers are held in memory and are not submitted to a department.</p>
  {#if forms.length}
    <label for="form">Choose a compiled form</label>
    <select id="form" bind:value={selectedId} disabled={busy || Boolean(run && !run.terminal)}>
      {#each forms as form}<option value={form.id}>{form.name} ({form.id})</option>{/each}
    </select>
    <button type="button" onclick={start} disabled={busy || !selectedId}>{run ? 'Restart form' : 'Start form'}</button>
  {:else if !error}
    <p>No compiled forms found. Compile a form and run the local preview API.</p>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if run?.interaction}
    {#key run.interaction.id}
      <section class="question">
        {#if presentation?.is_first_field && presentation?.page_heading}<h2>{String(presentation.page_heading)}</h2>{/if}
        {#if presentation?.is_first_field && presentation?.guidance_markdown}<pre class="guidance">{String(presentation.guidance_markdown)}</pre>{/if}
        <h2>{String(presentation?.question_text || run.interaction.content?.description || '')}</h2>
        {#if presentation?.field_label}<p class="field-label">{String(presentation.field_label)}</p>{/if}
        <SchemaForm interaction={run.interaction} disabled={busy} proposedValues={null}
          onSubmit={submit} onClearSuggestedValues={() => {}} />
      </section>
    {/key}
  {:else if run?.terminal}
    <section class="question"><h2>Answers collected</h2><p>Preview complete. No submission or payment has taken place.</p>
      <details><summary>Review collected synthetic answers</summary><pre>{JSON.stringify(run.answers, null, 2)}</pre></details>
    </section>
  {/if}
</main>
<style>
  :global(body) { margin: 0; background: #f3f2f1; color: #0b0c0c; font-family: Arial, sans-serif; }
  main { max-width: 750px; margin: 2rem auto; padding: 0 1.5rem 4rem; }
  a { color: #1d70b8; } .tag { font-weight: bold; border-left: 5px solid #1d70b8; padding-left: .8rem; }
  h1 { font-size: 2.3rem; } h2 { font-size: 1.5rem; }
  .question { background: white; border-top: 5px solid #1d70b8; padding: 1.5rem; margin-top: 2rem; }
  .guidance { font: inherit; white-space: pre-wrap; line-height: 1.5; }
  .field-label { font-weight: bold; }
  label { display: block; font-weight: bold; margin: 1rem 0 .5rem; }
  select { min-height: 2.5rem; padding: .4rem; max-width: 100%; }
  button { display: block; background: #00703c; color: white; border: 0; padding: .75rem 1rem; margin-top: 1rem; cursor: pointer; }
  button:disabled { opacity: .55; } .error { border-left: 5px solid #d4351c; padding: .75rem; background: white; }
  pre { overflow-x: auto; }
</style>
