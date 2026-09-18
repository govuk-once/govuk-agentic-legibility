const MAX_CHARACTERS_PER_LINK = 20000;
const FETCH_TIMEOUT_MS = 10000;

export type FetchedLink = { url: string; text: string } | { url: string; error: string };

/**
 * Fetches a service link and reduces it to plain text for the generation prompt. This is a
 * lightweight regex implementation, not a real HTML to text pass. Intended as a proof of concept right now to see if webpage content is a useful addition to generating schemas.
 * At the moment it does not separate the main article from navigation, footer or cookie
 * banner text. A failed fetch is returned as an error rather than thrown, so one bad link does not
 * stop the rest of the schema being built. if the proof of concept works it will need replacing with a Agent Core browser tool call that handles web browsing more ffectively.
 */
export async function fetchLinkText(url: string): Promise<FetchedLink> {
	try {
		const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
		if (!response.ok) {
			return { url, error: `Responded with status ${response.status}` };
		}

		const html = await response.text();
		const text = html
			.replace(/<script[\s\S]*?<\/script>/gi, ' ')
			.replace(/<style[\s\S]*?<\/style>/gi, ' ')
			.replace(/<[^>]+>/g, ' ')
			.replace(/\s+/g, ' ')
			.trim()
			.slice(0, MAX_CHARACTERS_PER_LINK);

		return { url, text };
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Unknown error';
		return { url, error: message };
	}
}
