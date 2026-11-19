import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

/**
 * Sends the address of the app to the start page, so a person always begins by choosing what to make.
 */
export const load: PageLoad = () => {
	redirect(307, '/onboard');
};
