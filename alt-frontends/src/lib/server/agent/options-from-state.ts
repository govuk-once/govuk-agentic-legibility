import type { AwaitingInput, RunStateDTO } from '$lib/types';

export interface OptionsResult {
  kind: string | null;
  options: string[];
}

// Port of durable_poc/agent/api/events.py:get_options_from_state.
export function getOptionsFromState(state: RunStateDTO | null): OptionsResult {
  if (!state) {
    return { kind: null, options: [] };
  }

  const awaiting = state.awaiting as (AwaitingInput & { state_type?: string | null }) | null;
  if (!awaiting) {
    return { kind: null, options: [] };
  }

  const schema = (awaiting.schema ?? {}) as unknown as Record<string, unknown>;
  const kind = (schema.kind as string | undefined) ?? awaiting.state_type ?? null;

  if (kind === 'boolean') {
    return { kind: 'boolean', options: ['Yes', 'No'] };
  }

  const nestedSchema = schema.schema;
  const rawOptions =
    awaiting.options ??
    schema.options ??
    (nestedSchema && typeof nestedSchema === 'object'
      ? (nestedSchema as Record<string, unknown>).options
      : null) ??
    [];

  if (!Array.isArray(rawOptions) || rawOptions.length === 0) {
    return { kind, options: [] };
  }

  const labelKey = schema.label_key as string | undefined;
  const valueKey = schema.value_key as string | undefined;

  const choices = rawOptions.map((opt: unknown) => {
    if (opt && typeof opt === 'object') {
      const o = opt as Record<string, unknown>;
      let label: unknown = labelKey && o[labelKey] != null ? o[labelKey] : null;

      if (label == null) {
        label =
          o.label ??
          o.single_line ??
          o.name ??
          o.title ??
          o.description ??
          (valueKey ? o[valueKey] : null) ??
          o.id ??
          o.value;
      }

      if (label == null) {
        const strVals = Object.values(o).filter((v) => typeof v === 'string');
        label = strVals.length > 0 ? strVals[0] : JSON.stringify(o);
      }

      return String(label);
    }
    return String(opt);
  });

  return { kind, options: choices };
}
