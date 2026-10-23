// Turns an answer into the plain text the Check your answers screen shows.

// Shared (src/lib/schema/kind.ts): field kinds and option lists
import { resolveChoices, resolveFieldKind } from '$lib/schema/kind';
// Shared (src/lib/types.ts): the question schema type
import type { SchemaDefinition } from '$lib/types';

/** Where an answer came from, which decides the small tag under it. */
export type AnswerSource = 'facts' | 'said' | 'confirmed';

export interface ReviewItem {
  token: string;
  value: unknown;
  source: AnswerSource;
  /** Text to show, when the caller keyed it. The agent's answers are worked out from the value. */
  display?: string;
}

/** The first line of a question, which is the question itself. */
export function questionLabel(prompt: string): string {
  return prompt.split('\n').find((line) => line.trim() !== '')?.trim() ?? prompt;
}

/** Shows a value the agent submitted, using the question's own options where it has them. */
export function displayValue(schema: SchemaDefinition | undefined, value: unknown): string {
  if (schema) {
    const kind = resolveFieldKind(schema);

    if (kind === 'boolean') {
      if (value === true || value === 'true') return 'Yes';
      if (value === false || value === 'false') return 'No';
    }

    if (kind === 'select_one' || kind === 'select_many') {
      const choices = resolveChoices(schema);
      const items = Array.isArray(value) ? value : [value];
      return items
        .map((item) => {
          // An address is picked by its reference number, which the agent can send as a number, so
          // a match on the option's value comes before reading it as a position in the list.
          if (typeof item === 'number') {
            const byValue = choices.find((choice) => choice.value === String(item));
            return byValue?.label ?? choices[item - 1]?.label ?? String(item);
          }
          if (typeof item === 'string') {
            const byValue = choices.find((choice) => choice.value === item);
            if (byValue) return byValue.label;
            const index = Number(item);
            if (Number.isInteger(index) && choices[index - 1]) return choices[index - 1].label;
            return item;
          }
          if (item && typeof item === 'object') {
            const record = item as Record<string, unknown>;
            return String(record.single_line ?? record.label ?? record.name ?? JSON.stringify(item));
          }
          return String(item);
        })
        .join(', ');
    }

    if (kind === 'file_ref' && value && typeof value === 'object') {
      return String((value as { ref?: unknown }).ref ?? 'File');
    }
  }

  if (typeof value === 'string') return value;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return JSON.stringify(value);
}
