import type { DraftLoad } from '$lib/drafts/draft-load';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import type { WorkingWorkflow } from '$lib/schema/workflow/working-process';

/*
	Holds a generated service draft in the browser tab so that the service editor can open it. The draft is generated
	on the server and shown on the onboarding page, and the editor is another page, so it needs storing between routes.
	Session storage lasts for the life of the tab and is never sent to a server, and it survives a reload of the
	editor. It is only a hand over and not a place to save work: changes made in the editor are not written back.

	Forms are saved as drafts that can be opened again, in drafts/draft-store.ts, so they do not use this hand over.
*/

const storageKey = 'service-studio.service-draft';

/**
 * Keeps a draft so the editor page can open it. It is stored as the manifest and its processes, which is the shape
 * that the schema check reads. Returns false when the browser would not store it, for example when site data is
 * blocked, so the caller can tell the person.
 */
export function saveDraft(workflow: WorkingWorkflow): boolean {
	try {
		sessionStorage.setItem(storageKey, JSON.stringify({ manifest: workflow.manifest, processes: workflow.processes }));
		return true;
	} catch {
		return false;
	}
}

/**
 * Reads the held draft and checks it against the schema, because whatever is in storage could have been changed
 * since it was saved. A draft that is not there, or cannot be read, comes back as a reason and not as a failure.
 */
export function loadDraft(): DraftLoad {
	let stored: string | null;
	try {
		stored = sessionStorage.getItem(storageKey);
	} catch {
		return { ok: false, reason: 'missing' };
	}
	if (stored === null) return { ok: false, reason: 'missing' };

	let parsed: unknown;
	try {
		parsed = JSON.parse(stored);
	} catch {
		return { ok: false, reason: 'invalid', issues: [{ path: '(root)', message: 'The saved draft is not valid JSON.' }] };
	}

	const result = parseWorkflow(parsed);
	return result.ok ? { ok: true, workflow: result.workflow } : { ok: false, reason: 'invalid', issues: result.issues };
}
