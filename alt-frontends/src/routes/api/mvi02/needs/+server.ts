import { json } from '@sveltejs/kit';
import { createConversation, stepConversation } from '$lib/server/agent/run-turn';
import type { RequestHandler } from './$types';

// For each thing a journey might ask the caller to upload, says whether the caller's facts already
// cover it. Advisory only: it just fills in the overview before the call, and the call itself
// still asks the real questions.

const SYSTEM_PROMPT = `You read a person's notes about themselves and say, for each thing a government service might ask for (a document, an upload, an address or a number such as a National Insurance number), whether the notes already settle it.

Respond with ONLY a single JSON object, no other text and no markdown code fences, mapping each need's key to:

{"status": "have" | "not_needed" | "unknown", "reason": "<short reason>"}

- "have": the notes say the person already has it or gives it (for example the address or number itself), or that it is already up to date or on file.
- "not_needed": the notes say it is not required, for example that they do not need a new photo.
- "unknown": the notes do not clearly say. This is the right answer whenever you are unsure.

Never guess. Only use what the notes clearly state.`;

interface NeedsBody {
  facts?: string;
  needs?: Array<{ key: string; label: string; prompt: string }>;
}

const STATUSES = ['have', 'not_needed', 'unknown'];

export const POST: RequestHandler = async ({ request }) => {
  const body = (await request.json().catch(() => ({}))) as NeedsBody;
  if (!body.facts?.trim() || !body.needs?.length) return json({ checks: {} });

  const prompt = [
    `Needs:\n${body.needs.map((need) => `- key: ${need.key}\n  what: ${need.label}\n  question the service asks: ${need.prompt}`).join('\n')}`,
    `The person's notes:\n${body.facts}`
  ].join('\n\n');

  try {
    const { responseText } = await stepConversation(createConversation([]), prompt, SYSTEM_PROMPT, []);
    const stripped = responseText.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
    const parsed = JSON.parse(stripped) as Record<string, { status?: unknown; reason?: unknown }>;

    const checks: Record<string, { status: string; reason: string }> = {};
    for (const need of body.needs) {
      const entry = parsed[need.key];
      if (entry && typeof entry.status === 'string' && STATUSES.includes(entry.status)) {
        checks[need.key] = { status: entry.status, reason: typeof entry.reason === 'string' ? entry.reason : '' };
      }
    }
    return json({ checks });
  } catch {
    // A failed model call just means nothing gets ticked.
    return json({ checks: {} });
  }
};
