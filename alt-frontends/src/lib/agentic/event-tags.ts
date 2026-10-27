// How an event from a run is labelled: the word on its tag, which colour the tag is, and how the
// engine's "waiting for an answer" line is picked out. The Activity list and the Event log both use it.

export interface RunEventLine {
  category?: string;
  summary?: string;
  detail?: unknown;
}

// "AGENT" becomes "Agent". Events from the person using the page are labelled "You".
export function categoryText(category: string | undefined): string {
  const text = category ?? 'Event';
  if (text.toLowerCase() === 'user') return 'You';
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

// The engine reports a question waiting for an answer as "Awaiting InputState [tkn_5]". This returns
// the token, or null for any other event.
export function awaitingToken(summary: string | undefined): string | null {
  return /^Awaiting InputState \[(.+)\]$/.exec(summary ?? '')?.[1] ?? null;
}

// Yellow marks a question waiting for an answer. Blue is for a person. The agent is purple, so it
// stands apart from the engine and the system, which are grey.
export function tagColour(line: RunEventLine): string {
  if (awaitingToken(line.summary)) return 'govuk-tag--yellow';
  const category = line.category?.toLowerCase();
  if (category === 'user') return 'govuk-tag--blue';
  if (category === 'agent') return 'govuk-tag--purple';
  return 'govuk-tag--grey';
}
