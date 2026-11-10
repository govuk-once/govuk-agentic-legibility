import { isAllowedLink } from './allowed-link-domains';

const MAX_CHARACTERS_PER_LINK = 20000;
const FETCH_TIMEOUT_MS = 10000;

// The most redirects that are followed before the link is given up on, so a loop cannot run for ever.
const MAX_REDIRECTS = 5;
const REDIRECT_STATUSES = [301, 302, 303, 307, 308];

const NOT_ON_THE_LIST = 'That site is not on the list of sites the assistant can read';
const REDIRECTED_OFF_THE_LIST = 'The link redirects to a site that is not on the list of sites the assistant can read';

export type FetchedLink = { url: string; text: string } | { url: string; error: string };

/**
 * Fetches a page, following redirects one at a time and checking every address against the list of sites the
 * assistant may read, so a page on a listed site cannot send the server on to somewhere else. The fetch is told not
 * to follow redirects itself, which is what lets each stop be checked. Gives the final response, or says why it
 * stopped.
 */
async function fetchOnTheList(start: string): Promise<{ response: Response } | { error: string }> {
	let address = start;

	for (let redirects = 0; redirects <= MAX_REDIRECTS; redirects += 1) {
		const response = await fetch(address, { redirect: 'manual', signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
		const location = response.headers.get('location');
		if (!REDIRECT_STATUSES.includes(response.status) || !location) return { response };

		// The body of a redirect is not needed, so it is closed to free the connection.
		await response.body?.cancel();
		address = new URL(location, address).href;
		if (!isAllowedLink(address)) return { error: REDIRECTED_OFF_THE_LIST };
	}

	return { error: 'The link redirects too many times' };
}

/**
 * Fetches a service link and reduces it to plain text for the generation prompt. Only a link on the list of sites
 * the assistant may read is fetched. This is a lightweight regex implementation, not a real HTML to text pass.
 * Intended as a proof of concept right now to see if webpage content is a useful addition to generating schemas.
 * At the moment it does not separate the main article from navigation, footer or cookie
 * banner text. A failed fetch is returned as an error rather than thrown, so one bad link does not
 * stop the rest of the schema being built. if the proof of concept works it will need replacing with a Agent Core browser tool call that handles web browsing more ffectively.
 */
export async function fetchLinkText(url: string): Promise<FetchedLink> {
	if (!isAllowedLink(url)) return { url, error: NOT_ON_THE_LIST };

	try {
		const fetched = await fetchOnTheList(url);
		if ('error' in fetched) return { url, error: fetched.error };

		const { response } = fetched;
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
