import { z } from 'zod';

/*
	What every kind of onboarding shares about the person's input: the details they typed on the details page, the
	version a first draft is given, the code made from a name, and the check on a link. A service and a form are
	drafted from the same details, so these live here and not with either one.
*/

// What the person typed on the details page: a name, a description, and the links the assistant should read.
export type OnboardDetails = { name: string; description: string; links: string[] };

// The version given to a first draft, for the workflow and for its process. Exported so a prompt can say the same.
export const firstVersion = '0.1.0';

/**
 * Turns a name into a short code that can be used in an id: lower case letters and numbers, with an underscore
 * between words. A name with nothing usable in it becomes "untitled", so an id is always possible.
 */
export function slugOf(name: string): string {
	const slug = name
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '_')
		.replace(/^_+|_+$/g, '');
	return slug || 'untitled';
}

// A link is only kept when it is a valid URL that uses http or https. The Zod option checks the scheme.
const webAddressSchema = z.url({ protocol: /^https?$/ });

/**
 * Tells whether a link the person typed is a web address, which is a valid URL that starts with http or https. The
 * assistant reads the pages behind the links to get context from what is already public, and the links are kept as
 * the sources of the draft. A link that is not a web address must be left out, or one typing mistake would make
 * the whole draft fail its check. Text with no scheme, such as gov.uk, and a link with another scheme, such as
 * mailto: or file:, are refused.
 */
export function isWebAddress(link: string): boolean {
	return webAddressSchema.safeParse(link).success;
}
