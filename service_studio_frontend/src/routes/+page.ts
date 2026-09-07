import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

/**
 * Redirects the former index route to the editor so existing entry links continue to work.
 */
export const load: PageLoad = () => {
	redirect(307, '/edit');
};
