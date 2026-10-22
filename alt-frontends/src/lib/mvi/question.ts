// Turns the run's current prompt into something the keypad can answer, and turns
// the keyed answer back into the value the run API expects.

// Shared: field kinds and option lists from src/lib/schema/kind.ts, prompt types from src/lib/types.ts
import { coerceSubmission, resolveChoices, resolveFieldKind, type Choice } from '$lib/schema/kind';
import type { AwaitingInput, PrefillSuggestion } from '$lib/types';
import { classifyString, type StringClassification } from './classify';
import { digitsToDate, formatDateDigits } from './format';

export type QuestionModel =
  // `byIndex`: send the option number rather than its value. The engine only turns a number into
  // the full option (an address, for example); an `enum` question takes its value as it is.
  | { type: 'choice'; multi: boolean; boolean: boolean; byIndex: boolean; choices: Choice[] }
  | { type: 'text'; classification: StringClassification }
  | { type: 'file' };

export function modelFor(awaiting: AwaitingInput): QuestionModel {
  const kind = resolveFieldKind(awaiting.schema);
  switch (kind) {
    case 'boolean':
      return {
        type: 'choice',
        multi: false,
        boolean: true,
        byIndex: false,
        choices: [
          { value: 'true', label: 'Yes' },
          { value: 'false', label: 'No' }
        ]
      };
    case 'select_one':
      return {
        type: 'choice',
        multi: false,
        boolean: false,
        byIndex: awaiting.schema.kind !== 'enum',
        choices: resolveChoices(awaiting.schema)
      };
    case 'select_many':
      return { type: 'choice', multi: true, boolean: false, byIndex: true, choices: resolveChoices(awaiting.schema) };
    case 'file_ref':
      return { type: 'file' };
    default:
      return { type: 'text', classification: classifyString(awaiting.schema) };
  }
}

/** Up to 9 options use a single key each; more than that needs a number typed in. */
export function usesSingleKey(count: number): boolean {
  return count <= 9;
}

/** The keys that can be pressed for a choice question. */
export function liveChoiceKeys(count: number): Set<string> {
  if (!usesSingleKey(count)) return new Set('0123456789'.split(''));
  const keys = new Set<string>();
  for (let n = 1; n <= count; n += 1) keys.add(String(n));
  return keys;
}

/** What a digit press does to the keyed choice number for a single-answer question. */
export function applyChoiceDigit(entry: string, digit: string, count: number): string {
  if (usesSingleKey(count)) {
    const n = Number(digit);
    return n >= 1 && n <= count ? digit : entry;
  }
  const appended = entry + digit;
  if (Number(appended) >= 1 && Number(appended) <= count) return appended;
  const n = Number(digit);
  return n >= 1 && n <= count ? digit : entry;
}

/** The 1-based option number a keyed entry points at, or null if it isn't one. */
export function choiceNumber(entry: string, count: number): number | null {
  if (!entry) return null;
  const n = Number(entry);
  return Number.isInteger(n) && n >= 1 && n <= count ? n : null;
}

/** 1-based option numbers a suggestion points at. */
export function suggestedNumbers(model: QuestionModel, suggestion: PrefillSuggestion | null): number[] {
  if (!suggestion || model.type !== 'choice' || suggestion.confidence === 'low') return [];
  const values = Array.isArray(suggestion.value) ? suggestion.value : [suggestion.value];
  const wanted = values.map((value) => String(value));
  return model.choices.flatMap((choice, index) => (wanted.includes(choice.value) ? [index + 1] : []));
}

/** A suggested text answer that is worth offering, or null. */
export function suggestedText(model: QuestionModel, suggestion: PrefillSuggestion | null): string | null {
  if (!suggestion || model.type !== 'text' || suggestion.confidence === 'low') return null;
  return typeof suggestion.value === 'string' && suggestion.value.trim() ? suggestion.value.trim() : null;
}

/** The value sent to the run API for a keyed text answer. */
export function textSubmission(classification: StringClassification, text: string): string {
  return classification.format === 'date' ? digitsToDate(text) : text.trim();
}

/** Whether a keyed text answer can be sent yet. */
export function textIsComplete(classification: StringClassification, text: string): boolean {
  if (classification.format === 'date' && text.length !== 8) return false;
  const value = textSubmission(classification, text);
  if (!value) return false;
  return classification.pattern ? classification.pattern.test(value) : true;
}

/** What the big readout shows for a keyed text answer. */
export function textReadout(classification: StringClassification, text: string): string {
  return classification.format === 'date' ? formatDateDigits(text) : text;
}

/** The value sent for a choice question. */
export function choiceSubmission(model: Extract<QuestionModel, { type: 'choice' }>, numbers: number[]): unknown {
  if (model.byIndex) return model.multi ? numbers : numbers[0];
  const values = numbers.map((n) => model.choices[n - 1].value);
  if (model.multi) return values;
  return coerceSubmission(model.boolean ? 'boolean' : 'select_one', values[0]);
}

/** Plain text for the list of answers shown when the call ends. */
export function choiceDisplay(model: Extract<QuestionModel, { type: 'choice' }>, numbers: number[]): string {
  return numbers.map((n) => model.choices[n - 1].label).join(', ');
}
