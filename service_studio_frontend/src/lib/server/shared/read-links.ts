import { fetchLinkText } from './fetch-link';

/**
 * Fetches every link the person gave and turns each page that could be read into a section of text for the
 * brief that is sent to the model. A link that could not be read does not stop the others: it is left out and
 * a warning says which one and why, so the person can see what the draft was not based on. Empty links are
 * skipped. The service and the form onboarding both need this, so it is kept here.
 */
export async function readLinks(links: string[]): Promise<{ sections: string[]; warnings: string[] }> {
	const fetched = await Promise.all(links.filter(Boolean).map(fetchLinkText));
	const warnings: string[] = [];

	const sections = fetched.flatMap((link) => {
		if ('error' in link) {
			warnings.push(`Could not read ${link.url}: ${link.error}`);
			return [];
		}
		return [`Source: ${link.url}\n${link.text}`];
	});

	return { sections, warnings };
}
