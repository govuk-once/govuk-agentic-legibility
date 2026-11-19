import { error } from '@sveltejs/kit';
import { createDraftStore } from '$lib/draft-store';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { checkLoadedForm } from './schema/form-states';

// The edited form, held in the browser tab when it is sent to tech review so the review pages after the editor can
// open it. It has its own key, so sending a form on never replaces a generated draft that has not been opened yet.
export const { saveDraft: saveFormForReview, loadDraft: loadFormForReview } = createDraftStore('service-studio.form-review');

/**
 * Opens the form held for the reviews, for a review's layout to load. A form that cannot be opened stops the review
 * with an error, and the review's error page says why: there was no form in the tab, or it did not match the schema.
 */
export function openFormForReview(): Workflow {
	const form = checkLoadedForm(loadFormForReview());
	if (form.ok) return form.workflow;
	if (form.reason === 'missing') error(404, { message: 'There is no form in this browser tab' });
	error(422, { message: 'The form did not match the required format', issues: form.issues });
}
