import { error } from '@sveltejs/kit';
import { loadFormForReview } from '$lib/form-editor/review-store';
import { checkLoadedForm } from '$lib/form-editor/schema/form-states';
import type { LayoutLoad } from './$types';

// The form sent on from the editor is held in this browser tab, so the pages are built in the browser and never on
// the server, where there is no tab to read it from.
export const ssr = false;

// Every step of the owner review works on the same form, so it is opened once here. A form that cannot be opened
// stops the review, and the error page says why.
export const load: LayoutLoad = () => {
	const form = checkLoadedForm(loadFormForReview());
	if (form.ok) return { workflow: form.workflow };
	if (form.reason === 'missing') error(404, { message: 'There is no form in this browser tab' });
	error(422, { message: 'The form did not match the required format', issues: form.issues });
};
