// What a journey asks the caller to have ready, read from its definition, and a check of those
// against the caller's facts.

// Shared (src/lib/graph/fsm.ts): the journey definition shape
import type { WorkflowDefinition } from '$lib/graph/fsm';
// Shared (src/lib/schema/kind.ts): tells a file upload apart from other questions
import { resolveFieldKind } from '$lib/schema/kind';
import type { SchemaDefinition } from '$lib/types';

export interface Need {
  key: string;
  /** What sort of thing it is, which decides its icon and what it says when the facts don't cover it. */
  kind: 'upload' | 'detail' | 'address' | 'payment';
  /** Set for a need that is settled whatever the facts say, such as a payment no journey asks for. */
  fixed?: 'none';
  /** What the caller needs, for example "Photo". */
  label: string;
  /** The question the journey asks for it, used when checking the facts. */
  prompt: string;
}

/** How the facts stand on a need. "have" and "not_needed" both mean nothing is left to ask. */
export type NeedStatus = 'have' | 'not_needed' | 'unknown';

export interface NeedCheck {
  status: NeedStatus;
  reason: string;
}

// "prompt_matb1_file" becomes "MATB1": noise words are dropped, and a word with a digit in it is
// an abbreviation, so it is upper-cased.
const NOISE = new Set(['prompt', 'upload', 'ask', 'file', 'form', 'update', 'api']);

function prettify(name: string): string {
  const words = name
    .split('_')
    .filter((word) => word !== '' && !NOISE.has(word))
    .map((word) => (/\d/.test(word) ? word.toUpperCase() : word));
  const text = words.join(' ');
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

// Names that read badly once the state's name is tidied, written out in full.
const FULL_NAMES: Record<string, string> = {
  MATB1: 'MAT B1 certificate',
  SMP1: 'SMP1 form',
  'Marriage cert': 'Marriage certificate'
};

/**
 * Everything the journey can ask the caller for: their address, a National Insurance number and any
 * uploads, found by reading its questions. Which of them a caller actually meets depends on their
 * answers along the way.
 */
export function needsFromDefinition(definition: WorkflowDefinition): Need[] {
  const address: Need[] = [];
  const details: Need[] = [];
  const uploads: Need[] = [];
  const seen = new Set<string>();

  for (const [processName, process] of Object.entries(definition.processes)) {
    for (const [stateName, state] of Object.entries(process.states)) {
      const key = `${processName}.${stateName}`;

      // Looking an address up is a call to the Post Office, so that counts as asking for one too.
      if (state.type === 'call' && state.service === 'postoffice' && !seen.has('address')) {
        seen.add('address');
        address.push({ key, kind: 'address', label: 'Your address', prompt: 'The person\'s address' });
      }
      if (state.type !== 'input') continue;

      const text = `${stateName} ${state.prompt}`;
      if (/address|postcode/i.test(text) && !seen.has('address')) {
        seen.add('address');
        address.push({ key, kind: 'address', label: 'Your address', prompt: 'The person\'s address' });
      }

      if (/national insurance/i.test(state.prompt)) {
        const label = /partner/i.test(state.prompt) ? "Partner's National Insurance number" : 'National Insurance number';
        if (!seen.has(label)) {
          seen.add(label);
          details.push({ key, kind: 'detail', label, prompt: state.prompt });
        }
      }

      if (resolveFieldKind(state.schema as unknown as SchemaDefinition) === 'file_ref') {
        // The state's own name says most, and the process it sits in is the fallback.
        const tidy = prettify(stateName) || prettify(processName) || 'A document';
        const label = FULL_NAMES[tidy] ?? tidy;
        if (!seen.has(label)) {
          seen.add(label);
          uploads.push({ key, kind: 'upload', label, prompt: state.prompt });
        }
      }
    }
  }

  // None of the journeys charge anything, so this is always shown as not needed. It stays on
  // the list so the caller can see that nothing has to be paid.
  const payment: Need = { key: 'payment', kind: 'payment', fixed: 'none', label: 'A way to pay', prompt: '' };
  return [...address, ...details, ...uploads, payment];
}

/** Asks the server which needs the facts already cover. Anything that goes wrong means "unknown". */
export async function checkNeeds(facts: string, needs: Need[]): Promise<Record<string, NeedCheck>> {
  const asked = needs.filter((need) => !need.fixed);
  if (!facts.trim() || asked.length === 0) return {};
  try {
    const response = await fetch('/api/mvi02/needs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ facts, needs: asked })
    });
    if (!response.ok) return {};
    const body = (await response.json()) as { checks?: Record<string, NeedCheck> };
    return body.checks ?? {};
  } catch {
    return {};
  }
}
