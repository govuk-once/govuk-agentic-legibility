import { goToChosenMethod } from '$lib/components/draft-methods';
import type { PageLoad } from './$types';

// Drafting with the assistant asks for the details of the form. Starting from an existing form goes straight to the
// list of forms in the editor, so nothing is generated.
export const load: PageLoad = ({ url }) => {
	goToChosenMethod(url, { automation: '/onboard/form/details', existing: '/edit-form' });
};
