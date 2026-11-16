import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { Pathname } from '$app/types';

/*
	The ways a person can choose to start a draft on the method page. The page posts the choice back to itself as
	a plain form, so it works without scripts, and the route's loader sends the person on to the page for that
	choice. Each kind of draft says which choices it offers and where each leads.
*/

export type DraftMethod = 'automation' | 'existing' | 'blank';

// The name the method page gives its choice, which the loader reads back from the address.
export const draftMethodField = 'draft-method';

/**
 * Sends the person on to the page for the choice they made on the method page. Nothing happens when no choice was
 * made, or the choice is not one this kind of draft offers, so the method page is shown again.
 */
export function goToChosenMethod(url: URL, routes: Partial<Record<DraftMethod, Pathname>>): void {
	const chosen = url.searchParams.get(draftMethodField);
	const route = chosen !== null && Object.hasOwn(routes, chosen) ? routes[chosen as DraftMethod] : undefined;
	if (route) redirect(303, resolve(route));
}
