import { error } from '@sveltejs/kit';
import { openDraft, readOpenDraft, saveDraft, type DraftStage, type ReviewProgress, type SavedDraft } from '$lib/drafts/draft-store';
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
 * Saves the draft from a review page, with the stage the draft is now at so it opens there when it is picked again,
 * and with whatever the page changed: the form, how far the reviews have got, or neither. Everything else is kept as
 * it was, because a review does not add or take away steps or move boxes. The promise is rejected when the browser
 * will not store the draft.
 */
export async function saveReviewedForm(
	draft: SavedDraft,
	changes: { stage: DraftStage; workflow?: Workflow; reviewProgress?: ReviewProgress }
): Promise<void> {
	await saveDraft({ ...draft, ...changes });
}

/**
 * Saves the draft as it is from a review page where nothing waits to be saved, because the page saves each change as
 * it is made or changes nothing, so the person can stop and come back to the review later. Gives true once it is
 * saved, as the Save draft button expects.
 */
export async function saveDraftAsItIs(draft: SavedDraft, stage: DraftStage): Promise<boolean> {
	await saveReviewedForm(draft, { stage });
	return true;
}
