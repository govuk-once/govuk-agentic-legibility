<script lang="ts">
  import { humaniseIdentifier, initialValues, validateValues } from '$lib/schema';
  import type { Interaction, JsonSchemaProperty } from '$lib/types';

  export let interaction: Interaction;
  export let disabled = false;
  export let proposedValues: Record<string, unknown> | null = null;
  export let onSubmit: (values: Record<string, unknown>) => void;
  export let onClearSuggestedValues: () => void;
  const schema = interaction.input_schema;
  const fields = Object.entries(schema.properties ?? {});
  let values: Record<string, unknown> = {
    ...initialValues(schema),
    ...(proposedValues ?? {})
  };
  let appliedProposal = proposedValues;
  let errors: Record<string, string> = {};

  $: if (proposedValues !== appliedProposal) {
    replaceProposal(proposedValues);
  }

  function replaceProposal(nextProposal: Record<string, unknown> | null): void {
    const nextValues = { ...values };
    const defaults = initialValues(schema);
    for (const [name, previousValue] of Object.entries(appliedProposal ?? {})) {
      if (nextValues[name] !== previousValue) continue;
      if (name in defaults) nextValues[name] = defaults[name];
      else delete nextValues[name];
    }
    values = { ...nextValues, ...(nextProposal ?? {}) };
    appliedProposal = nextProposal;
    errors = {};
  }

  function clearSuggestedValues(): void {
    values = initialValues(schema);
    appliedProposal = null;
    errors = {};
    onClearSuggestedValues();
  }

  function setValue(name: string, value: unknown): void {
    values = { ...values, [name]: value };
    if (errors[name]) {
      const next = { ...errors };
      delete next[name];
      errors = next;
    }
  }
  function textValue(name: string, event: Event): void {
    setValue(name, (event.currentTarget as HTMLInputElement).value);
  }

  function numberValue(name: string, event: Event): void {
    const raw = (event.currentTarget as HTMLInputElement).value;
    setValue(name, raw === '' ? '' : Number(raw));
  }
  function selectValue(name: string, property: JsonSchemaProperty, event: Event): void {
    const raw = (event.currentTarget as HTMLSelectElement).value;
    setValue(name, property.enum?.find((value) => String(value) === raw) ?? raw);
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    errors = validateValues(schema, values);
    if (Object.keys(errors).length === 0) onSubmit(values);
  }
  function label(name: string, property: JsonSchemaProperty): string {
    return property.title || humaniseIdentifier(name);
  }

  function required(name: string): boolean {
    return schema.required?.includes(name) ?? false;
  }
  function renderableType(property: JsonSchemaProperty): string | undefined {
    if (property.type === undefined) return 'string';
    const types = Array.isArray(property.type) ? property.type : [property.type];
    const nonNullTypes = types.filter((type) => type !== 'null');
    return nonNullTypes.length === 1 ? nonNullTypes[0] : undefined;
  }
  function schemaTypeLabel(property: JsonSchemaProperty): string {
    if (property.type === undefined) return 'unspecified';
    return Array.isArray(property.type) ? property.type.join(', ') : property.type;
  }
</script>

<form onsubmit={submit} novalidate>
  {#if proposedValues}
    <div class="suggestion" role="status">
      <div>
        <strong>Values suggested from the conversation</strong>
        <span>Check or change them before continuing.</span>
      </div>
      <button class="clear" type="button" onclick={clearSuggestedValues} {disabled}>
        Clear suggested values
      </button>
    </div>
  {/if}
  {#if fields.length === 0}
    <div class="unsupported" role="alert">This interaction has no renderable form properties.</div>
  {/if}
  {#each fields as [name, property]}
    <div class:error={Boolean(errors[name])} class="field">
      {#if renderableType(property) === 'boolean'}
        <fieldset>
          <legend>{label(name, property)} {#if !required(name)}<span>(optional)</span>{/if}</legend>
          {#if property.description}<p class="hint">{property.description}</p>{/if}
          {#if errors[name]}<p class="error-message">{errors[name]}</p>{/if}
          <label class="choice"><input type="radio" {name} checked={values[name] === true} onchange={() => setValue(name, true)} {disabled} /> <span>Yes</span></label>
          <label class="choice"><input type="radio" {name} checked={values[name] === false} onchange={() => setValue(name, false)} {disabled} /> <span>No</span></label>
        </fieldset>
      {:else if property.enum}
        <label for={name}>{label(name, property)} {#if !required(name)}<span>(optional)</span>{/if}</label>
        {#if property.description}<p class="hint">{property.description}</p>{/if}
        {#if errors[name]}<p class="error-message">{errors[name]}</p>{/if}
        <select id={name} value={values[name] === undefined ? '' : String(values[name])} onchange={(event) => selectValue(name, property, event)} {disabled}>
          <option value="">Select an option</option>
          {#each property.enum as option}<option value={String(option)}>{String(option)}</option>{/each}
        </select>
      {:else if renderableType(property) === 'string'}
        <label for={name}>{label(name, property)} {#if !required(name)}<span>(optional)</span>{/if}</label>
        {#if property.description}<p class="hint">{property.description}</p>{/if}
        {#if errors[name]}<p class="error-message">{errors[name]}</p>{/if}
        <input id={name} type="text" value={String(values[name] ?? '')} oninput={(event) => textValue(name, event)} aria-invalid={errors[name] ? 'true' : undefined} {disabled} />
      {:else if renderableType(property) === 'number' || renderableType(property) === 'integer'}
        <label for={name}>{label(name, property)} {#if !required(name)}<span>(optional)</span>{/if}</label>
        {#if property.description}<p class="hint">{property.description}</p>{/if}
        {#if errors[name]}<p class="error-message">{errors[name]}</p>{/if}
        <input id={name} type="number" step={renderableType(property) === 'integer' ? '1' : 'any'} value={String(values[name] ?? '')} oninput={(event) => numberValue(name, event)} aria-invalid={errors[name] ? 'true' : undefined} {disabled} />
      {:else}
        <div class="unsupported" role="alert"><strong>{label(name, property)}</strong>: schema type <code>{schemaTypeLabel(property)}</code> is not supported by this prototype.</div>
      {/if}
    </div>
  {/each}
  {#if fields.length > 0}<button type="submit" {disabled}>{disabled ? 'Submitting…' : 'Continue'}</button>{/if}
</form>
<style>
  form { margin-top: 1.75rem; }
  .suggestion { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: 1.5rem; border-left: .3rem solid #00703c; background: #f3f2f1; padding: .8rem .9rem; }
  .suggestion div { display: grid; gap: .15rem; }
  .suggestion span { color: #505a5f; font-size: .88rem; }
  .clear { border: 2px solid #0b0c0c; border-bottom-width: 2px; background: #fff; color: #0b0c0c; box-shadow: none; padding: .45rem .65rem; white-space: nowrap; }
  .field { margin-bottom: 1.75rem; }
  .field.error { border-left: .3rem solid #d4351c; padding-left: .9rem; }
  fieldset { border: 0; padding: 0; margin: 0; }
  legend, label:not(.choice) { display: block; margin-bottom: .45rem; font-size: 1.05rem; font-weight: 700; }
  legend span, label span { color: #505a5f; font-weight: 400; }
  .hint { margin: 0 0 .65rem; color: #505a5f; }
  .error-message { margin: 0 0 .65rem; color: #d4351c; font-weight: 700; }
  input[type='text'], input[type='number'], select { box-sizing: border-box; width: min(100%,32rem); min-height: 2.75rem; border: 2px solid #0b0c0c; background: #fff; padding: .45rem .55rem; font: inherit; }
  input:focus, select:focus { outline: .2rem solid #ffdd00; outline-offset: 0; box-shadow: inset 0 0 0 2px #0b0c0c; }
  .choice { display: flex; align-items: center; gap: .7rem; width: fit-content; margin: .65rem 0; cursor: pointer; font-size: 1.05rem; }
  .choice input { width: 1.6rem; height: 1.6rem; margin: 0; accent-color: #1d70b8; }
  button { border: 0; border-bottom: .2rem solid #002d18; background: #00703c; color: #fff; padding: .72rem 1.25rem .62rem; font: inherit; font-weight: 700; cursor: pointer; box-shadow: 0 .15rem 0 #002d18; }
  button:hover:not(:disabled) { background: #005a30; }
  .clear:hover:not(:disabled) { background: #e8f1f8; }
  button:focus { outline: .2rem solid #ffdd00; outline-offset: .15rem; }
  button:disabled { cursor: wait; opacity: .55; }
  .unsupported { margin: 1rem 0; border-left: .3rem solid #f47738; background: #fff7e6; padding: .8rem 1rem; }
  code { background: #f3f2f1; padding: .1rem .25rem; }
  @media (max-width: 38rem) { .suggestion { align-items: flex-start; flex-direction: column; } }
</style>
