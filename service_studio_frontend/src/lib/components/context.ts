// Context a person adds to a step for the agent to read. This is a prototype of the interaction only: the
// items live in the editor page's own state and are not part of the canonical service schema.

export type ContextUrlItem = {
	id: string;
	kind: 'url';
	url: string;
	// What the page is for, in the person's own words. Optional, and used as the card's title when given.
	purpose: string;
};

export type ContextNoteItem = {
	id: string;
	kind: 'note';
	text: string;
};

export type ContextItem = ContextUrlItem | ContextNoteItem;

export const NOTE_MAX_LENGTH = 500;

/**
 * Checks that a web address someone typed is one the agent could actually fetch: it must parse as a URL
 * and use http or https. Returns the trimmed address when it is fine, or a message in plain English for
 * the error shown beside the field when it is not.
 */
export function parseContextUrl(input: string): { ok: true; url: string } | { ok: false; error: string } {
	const trimmed = input.trim();
	if (!trimmed) return { ok: false, error: 'Enter a web address' };

	let parsed: URL;
	try {
		parsed = new URL(trimmed);
	} catch {
		return { ok: false, error: 'Enter a web address in the correct format, like https://www.gov.uk' };
	}

	if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
		return { ok: false, error: 'Enter a web address that starts with https://' };
	}
	return { ok: true, url: trimmed };
}

/**
 * Shortens a web address for display: no scheme, no leading www and no trailing slash, so
 * https://www.gov.uk/change-address/ reads as gov.uk/change-address. Falls back to the text as typed if it
 * cannot be parsed, so a card never shows nothing.
 */
export function displayUrl(url: string): string {
	try {
		const parsed = new URL(url);
		const host = parsed.host.replace(/^www\./, '');
		const path = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/$/, '');
		return `${host}${path}${parsed.search}`;
	} catch {
		return url;
	}
}
