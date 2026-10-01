import type { SchemaDefinition } from '$lib/types';

export type FieldKind = 'boolean' | 'string' | 'select_one' | 'select_many' | 'file_ref';

export interface Choice {
  value: string;
  label: string;
}

/** Maps a raw `schema.kind` onto the KindField variant that renders it. */
export function resolveFieldKind(schema: SchemaDefinition): FieldKind {
  switch (schema.kind) {
    case 'boolean':
      return 'boolean';
    case 'select_one':
    case 'enum':
      return 'select_one';
    case 'select_many':
      return 'select_many';
    case 'file_ref':
      return 'file_ref';
    default:
      return 'string';
  }
}

/**
 * Normalizes the two option shapes the SFSM schema uses — a `schema.options`
 * list (OptionItem | string | free-form dict, keyed by `label_key`/`value_key`)
 * and the `enum` kind's separate `values`/`labels` pair — into one
 * `{value, label}` list for select_one/select_many rendering.
 */
export function resolveChoices(schema: SchemaDefinition): Choice[] {
  if (schema.values) {
    return schema.values.map((value) => ({
      value,
      label: schema.labels?.[value] ?? value
    }));
  }

  if (!schema.options) {
    return [];
  }

  const labelKey = schema.label_key;
  const valueKey = schema.value_key;

  return schema.options.map((opt, index) => {
    if (typeof opt === 'string') {
      return { value: opt, label: opt };
    }
    const record = opt as Record<string, unknown>;
    const value = String((valueKey && record[valueKey]) ?? record.value ?? record.id ?? index);
    const label = String(
      (labelKey && record[labelKey]) ??
        record.label ??
        record.single_line ??
        record.name ??
        record.title ??
        value
    );
    return { value, label };
  });
}

/** Coerces a form value into the shape `submit_input` expects for this kind. */
export function coerceSubmission(kind: FieldKind, raw: unknown): unknown {
  if (kind === 'boolean') {
    return raw === true || raw === 'true' || raw === 'Yes';
  }
  if (kind === 'select_many') {
    return Array.isArray(raw) ? raw : [raw].filter((v) => v !== undefined && v !== '');
  }
  return raw;
}
