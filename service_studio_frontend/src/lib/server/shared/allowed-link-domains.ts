import { isWebAddress } from './onboard-details';

/*
	The sites whose pages the assistant may read. A person types links on the details page, and the server fetches the
	pages behind them to give the assistant context from what is already published. Fetching any link a person types
	would let the server be pointed at addresses that only it can reach, such as its own machine or its private
	network, so only pages on a short list of sites are fetched. To allow another site, add its domain to the list.
*/

// A domain on the list allows itself and every subdomain of it, so gov.uk allows www.gov.uk as well.
export const allowedLinkDomains: readonly string[] = ['gov.uk'];

/**
 * Tells whether a link is on the list. It must be a web address that uses http or https, with no user name or
 * password in it and no unusual port, and its host must be a listed domain or a subdomain of one. The host is
 * compared as a whole, so evilgov.uk and gov.uk.example.com do not match gov.uk. The domains are passed in so a
 * test can use a list of its own.
 */
export function isAllowedLink(link: string, domains: readonly string[] = allowedLinkDomains): boolean {
	if (!isWebAddress(link)) return false;

	const { hostname, username, password, port } = new URL(link);
	if (username || password || port) return false;

	return domains.some((domain) => hostname === domain || hostname.endsWith(`.${domain}`));
}
