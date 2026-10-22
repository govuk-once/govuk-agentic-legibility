import type { SchemaDefinition } from '$lib/types';

// Decides how a `string` question is keyed on the keypad. The schemas' patterns are
// a mix of regexes (dates, sort codes, NINOs, postcodes).
//This is a prototyping approach for this demo but should be replaced with a regex parsing library in a scalable update
// or alternatively the schema should have an optional field to determine if its
//"date" | "digits" | "text". However, since this is a proof of concept that may not go further the prototype technique is a placeholder for now.


export type StringFormat = 'date' | 'digits' | 'text';

export interface StringClassification {
  format: StringFormat;
  /** Which keypad mode the question starts in. */
  startMode: 'digits' | 'letters';
  maxLength: number;
  pattern: RegExp | null;
}

const DATE_SAMPLE = '21/01/1986';
const LETTER_SAMPLE = 'ABCDEFGH';
const DIGIT_SAMPLES = ['123456', '12345678', '123456789', '1234567890', '07700900123'];

/** Matches the way the mock engine checks a pattern: anchored at the start. */
export function compilePattern(pattern?: string | null): RegExp | null {
  if (!pattern) return null;
  try {
    return new RegExp(`^(?:${pattern})`);
  } catch {
    return null;
  }
}

export function classifyString(schema: SchemaDefinition): StringClassification {
  const pattern = compilePattern(schema.pattern);

  if (pattern && !pattern.test(LETTER_SAMPLE)) {
    if (pattern.test(DATE_SAMPLE)) {
      return { format: 'date', startMode: 'digits', maxLength: 8, pattern };
    }
    if (DIGIT_SAMPLES.some((sample) => pattern.test(sample))) {
      return { format: 'digits', startMode: 'digits', maxLength: 20, pattern };
    }
  }

  return { format: 'text', startMode: 'letters', maxLength: schema.max_length ?? 100, pattern };
}
