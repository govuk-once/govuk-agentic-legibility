import { error } from '@sveltejs/kit';
import { openDraft, readOpenDraft, saveDraft, type DraftStage, type SavedDraft } from '$lib/drafts/draft-store';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { checkLoadedForm } from './schema/form-states';

/*
	Opens and saves the draft that the owner review and the technical review work on. It is the draft open in this
	browser tab, which the editor saved when the form was sent on. Unlike the editor, the reviews need a finished form,
	so the form is checked against the schema when it is opened.
*/

/**
 * Opens the draft open in this browser tab, for a review's layout to load, with its form checked against the schema.
 * A draft that cannot be opened stops the review with an error, and the review's error page says why: there was no
 * draft in the tab, or its form did not match the schema.
 */
export async function openDraftForReview(): Promise<{ draft: SavedDraft; workflow: Workflow }> {
	const id = readOpenDraft();
	const opened = id ? await openDraft(id) : undefined;
	if (!opened?.ok) {
		if (opened?.reason === 'unreadable') error(422, { message: 'The saved draft could not be read' });
		error(404, { message: 'There is no form in this browser tab' });
	}

	const parsed = parseWorkflow(opened.draft.workflow);
	const form = checkLoadedForm(parsed.ok ? { ok: true, workflow: parsed.workflow } : { ok: false, reason: 'invalid', issues: parsed.issues });
	if (!form.ok) {
		const issues = form.reason === 'invalid' ? form.issues : [];
		error(422, { message: 'The form did not match the required format', issues });
	}
	return { draft: opened.draft, workflow: form.workflow };
}

/**
 * Saves a change made in a review into its draft, with the stage the draft is now at, so the draft opens there when
 * it is picked again. The name and where the boxes were dragged to are kept as they were. The promise is rejected
 * when the browser will not store the draft.
 */
export async function saveReviewedForm(draft: SavedDraft, workflow: Workflow, stage: DraftStage): Promise<void> {
	await saveDraft({ id: draft.id, name: draft.name, stage, workflow, positions: draft.positions });
}
