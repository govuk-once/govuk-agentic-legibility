import { parseWorkflow, type WorkflowIssue } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	Holds a generated draft in the browser tab so that the editor can open it. The draft is generated on the server
	and shown on the onboarding page, and the editor is another page, so something has to carry it across. Session
	storage lasts for the life of the tab and is never sent to a server, and it survives a reload of the editor.
	It is only a hand over and not a place to save work: changes made in the editor are not written back.
*/

// The name the draft is kept under. It is specific to the service route, so the form route can keep its own.
const draftKey = 'service-studio.service-draft';

export type DraftLoad =
	| { ok: true; workflow: Workflow }
	| { ok: false; reason: 'missing' }
	| { ok: false; reason: 'invalid'; issues: WorkflowIssue[] };

/**
 * Keeps a draft so the editor can open it. It is stored as the manifest and its processes, which is the shape that
 * the schema check reads, and it is checked again when it is loaded. Returns false when the browser would not
 * store it, for example when site data is blocked, so the caller can tell the person.
 */
export function saveDraft(workflow: Workflow): boolean {
	try {
		sessionStorage.setItem(draftKey, JSON.stringify({ manifest: workflow.manifest, processes: workflow.processes }));
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
		stored = sessionStorage.getItem(draftKey);
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
