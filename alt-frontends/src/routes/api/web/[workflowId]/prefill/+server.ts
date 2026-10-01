import { json } from '@sveltejs/kit';
import { resolveChoices, resolveFieldKind } from '$lib/schema/kind';
import { buildPrefillPrompt, PREFILL_SYSTEM_PROMPT } from '$lib/server/agent/prefill-prompt';
import { createConversation, stepConversation } from '$lib/server/agent/run-turn';
import { getWebContext } from '$lib/server/agent/web-context-store';
import type { AwaitingInput, PrefillSuggestion } from '$lib/types';
import type { RequestHandler } from './$types';

interface PrefillRequestBody {
  awaiting: AwaitingInput;
}

interface RawSuggestion {
  value: unknown;
  confidence?: unknown;
  reason?: unknown;
}

function parseModelJson(text: string): RawSuggestion | null {
  const stripped = text.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  try {
    const parsed = JSON.parse(stripped) as unknown;
    if (parsed && typeof parsed === 'object' && 'value' in parsed) {
      return parsed as RawSuggestion;
    }
  } catch {
    // Fall through to null below — an unparsable response is treated as "no suggestion".
  }
  return null;
}

// Validates an LLM-suggested value against the real schema before it's ever
// shown to the user — mirrors system-prompt.ts's option-matching and
// file_ref rules so a bad/hallucinated suggestion is silently discarded
// rather than surfaced.
function validateValue(awaiting: AwaitingInput, value: unknown): unknown {
  const kind = resolveFieldKind(awaiting.schema);

  if (kind === 'file_ref') {
    return null;
  }
  if (kind === 'boolean') {
    return typeof value === 'boolean' ? value : null;
  }
  if (kind === 'select_one') {
    if (typeof value !== 'string') return null;
    const choices = resolveChoices(awaiting.schema);
    return choices.some((c) => c.value === value) ? value : null;
  }
  if (kind === 'select_many') {
    if (!Array.isArray(value)) return null;
    const choices = resolveChoices(awaiting.schema);
    const valid = value.filter((v) => typeof v === 'string' && choices.some((c) => c.value === v));
    return valid.length > 0 ? valid : null;
  }
  return typeof value === 'string' && value.trim() ? value : null;
}

export const POST: RequestHandler = async ({ params, request }) => {
  const workflowId = params.workflowId!;
  const body = (await request.json()) as PrefillRequestBody;
  const awaiting = body.awaiting;

  const contextText = getWebContext(workflowId);
  if (!awaiting || !contextText) {
    return json({ suggestion: null });
  }

  try {
    const prompt = buildPrefillPrompt(awaiting, contextText);
    const { responseText } = await stepConversation(
      createConversation([]),
      prompt,
      PREFILL_SYSTEM_PROMPT,
      []
    );

    const raw = parseModelJson(responseText);
    if (!raw) {
      return json({ suggestion: null });
    }

    const value = validateValue(awaiting, raw.value);
    if (value === null || value === undefined) {
      return json({ suggestion: null });
    }

    const confidence =
      raw.confidence === 'high' || raw.confidence === 'medium' || raw.confidence === 'low'
        ? raw.confidence
        : 'low';

    const suggestion: PrefillSuggestion = {
      value,
      confidence,
      reason: typeof raw.reason === 'string' ? raw.reason : 'from your notes'
    };
    return json({ suggestion });
  } catch {
    // Advisory feature: any failure (LLM error, parsing, etc.) degrades to
    // no suggestion rather than breaking the deterministic /web form flow.
    return json({ suggestion: null });
  }
};
