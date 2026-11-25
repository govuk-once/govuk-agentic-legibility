import type { AwaitingInput } from '$lib/types';
import { resolveChoices, resolveFieldKind } from '$lib/schema/kind';

// A one-shot, non-tool-calling extraction prompt: given free-text notes a
// /web user has opted to provide, suggest a value for the single field
// currently awaited. This is advisory only — the suggestion pre-fills the
// existing KindField form, which the user can edit or ignore, and Temporal
// still independently validates whatever is actually submitted.
export const PREFILL_SYSTEM_PROMPT = `You suggest a pre-filled value for one form field, extracted from a user's free-text notes.

## Output format

Respond with ONLY a single JSON object, no other text, no markdown code fences:

{"value": <value-or-null>, "confidence": "high" | "medium" | "low", "reason": "<short reason>"}

If the notes don't contain a confident answer for this specific field, respond with {"value": null, "confidence": "low", "reason": "not mentioned in notes"}.

## Rules by field kind

- **boolean**: \`value\` must be a JSON boolean (\`true\`/\`false\`), or \`null\` if not stated.
- **string**: \`value\` must be a plain JSON string, exactly as it should appear in the field — never wrap it in extra quotes.
- **select_one**: \`value\` must be exactly one of the option \`value\`s listed below, or \`null\` if none match.
- **select_many**: \`value\` must be a JSON array containing only option \`value\`s listed below, or \`null\`.
- **file_ref**: ALWAYS respond with \`value: null\`. Never fabricate a file reference, filename, content type, or byte size — files can only come from an actual upload.

Never invent a value that isn't clearly supported by the notes. When in doubt, return \`null\` with \`"confidence": "low"\`.`;

export function buildPrefillPrompt(awaiting: AwaitingInput, contextText: string): string {
  const kind = resolveFieldKind(awaiting.schema);
  const choices = resolveChoices(awaiting.schema);

  const parts = [
    `Field kind: ${kind}`,
    `Field prompt: ${awaiting.prompt}`,
    `Field schema: ${JSON.stringify(awaiting.schema)}`
  ];

  if (choices.length > 0) {
    parts.push(`Valid option values: ${JSON.stringify(choices.map((c) => c.value))}`);
  }

  parts.push(`User's notes:\n${contextText}`);

  return parts.join('\n\n');
}
