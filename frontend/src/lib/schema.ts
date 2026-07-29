import type { JsonSchema } from '$lib/types';

export function humaniseIdentifier(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function initialValues(schema: JsonSchema): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(schema.properties ?? {})
      .filter(([, property]) => property.default !== undefined)
      .map(([name, property]) => [name, property.default])
  );
}

export function validateValues(
  schema: JsonSchema,
  values: Record<string, unknown>
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const name of schema.required ?? []) {
    const value = values[name];
    if (value === undefined || value === null || value === '') {
      errors[name] = 'Enter a value';
    }
  }
  return errors;
}

export function flattenData(value: unknown, prefix = ''): Array<[string, string]> {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => flattenData(item, `${prefix} ${index + 1}`.trim()));
  }
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).flatMap(([key, child]) =>
      flattenData(child, `${prefix} ${humaniseIdentifier(key)}`.trim())
    );
  }
  if (value === undefined || value === null) {
    return [];
  }
  return [[prefix || 'Value', String(value)]];
}
