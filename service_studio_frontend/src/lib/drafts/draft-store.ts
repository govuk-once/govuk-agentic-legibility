import { z } from 'zod';
import type { NodePositions } from '$lib/process-graph/process-graph-types';
import type { WorkingWorkflow } from '$lib/schema/workflow/working-process';

/*
	Saves forms that are still being worked on, so a person can leave one and come back to it, and move it between the
	editor and the reviews. Drafts are kept in the browser's local storage for now. Each of the four actions returns a
	promise and matches one call to a file store such as Amazon S3: saveDraft writes a file, openDraft reads one,
	listDrafts lists them and deleteDraft removes one. When drafts move to a server, only the inside of these four
	functions changes, and every page that awaits them stays as it is.

	The draft that is open in this browser tab is remembered separately, in session storage, so the editor and the
	review pages know which draft to open without the person picking it on every page.
*/

// The stages a draft can be left at, named as they are in the progress banner, so a draft opens where it was left.
export const draftStages = ['Edit', 'Owner review', 'Tech review'] as const;

export type DraftStage = (typeof draftStages)[number];

// What the list of drafts shows about each one, without the form itself.
export interface DraftSummary {
	id: string;
	name: string;
	stage: DraftStage;
	// When the draft was last saved, as an ISO date and time, set by saveDraft and not by the page.
	savedAt: string;
}

// A whole saved draft: the form as the editor holds it and where its boxes were dragged to on the graph.
export interface SavedDraft extends DraftSummary {
	workflow: WorkingWorkflow;
	positions: NodePositions;
}

// What opening a draft gives back. The form inside a draft that opens is not checked against the schema here,
// because a draft can be saved while the journey still has loose pieces. Each page checks it as strictly as it needs.
export type DraftOpen = { ok: true; draft: SavedDraft } | { ok: false; reason: 'missing' | 'unreadable' };

// Every draft is kept under this prefix and its id, so the drafts can be found among anything else the site stores.
const draftKeyPrefix = 'service-studio.draft.';

// Where the id of the draft open in this tab is kept.
const openDraftKey = 'service-studio.open-draft';

// The parts of a stored draft that are checked when it is read back. The form is checked only to have a manifest and
// processes, with the process the manifest names as its entry among them, because an editor opens that process. The
// rest of the form is not checked, for the reason given on DraftOpen.
const storedDraftSchema = z.object({
	id: z.string().min(1),
	name: z.string(),
	stage: z.enum(draftStages),
	savedAt: z.iso.datetime(),
	workflow: z
		.object({ manifest: z.looseObject({ entry: z.string() }), processes: z.record(z.string(), z.unknown()) })
		.refine((workflow) => workflow.manifest.entry in workflow.processes, 'The entry process is not in the draft'),
	positions: z.record(z.string(), z.object({ x: z.number(), y: z.number() }))
});

/**
 * Reads one stored draft and checks its shape. Something that is not JSON, or not shaped like a draft, gives
 * nothing back, because storage could have been changed by hand since the draft was saved.
 */
function readStoredDraft(key: string): SavedDraft | undefined {
	const stored = localStorage.getItem(key);
	if (stored === null) return undefined;
	try {
		const result = storedDraftSchema.safeParse(JSON.parse(stored));
		// The form passed the loose check above and is held in its editing shape, which the page checks further.
		return result.success ? (result.data as SavedDraft) : undefined;
	} catch {
		return undefined;
	}
}

/**
 * Saves a draft, creating it or replacing the one with the same id, and gives back the draft as it was saved with
 * the time it was saved. The promise is rejected when the browser will not store it, for example when site data is
 * blocked or storage is full, so the page can tell the person it was not saved.
 */
export async function saveDraft(draft: Omit<SavedDraft, 'savedAt'>): Promise<SavedDraft> {
	// Only the manifest and processes of the form are kept, which is the shape the schema check reads.
	const saved: SavedDraft = {
		...draft,
		workflow: { manifest: draft.workflow.manifest, processes: draft.workflow.processes },
		savedAt: new Date().toISOString()
	};
	localStorage.setItem(draftKeyPrefix + draft.id, JSON.stringify(saved));
	return saved;
}

/**
 * Opens one draft by its id. A draft that is not there says it is missing, and one that cannot be read says so,
 * so the page can tell the person which it was.
 */
export async function openDraft(id: string): Promise<DraftOpen> {
	const key = draftKeyPrefix + id;
	if (localStorage.getItem(key) === null) return { ok: false, reason: 'missing' };
	const draft = readStoredDraft(key);
	return draft ? { ok: true, draft } : { ok: false, reason: 'unreadable' };
}

/**
 * Lists every saved draft, the most recently saved first, for the list of drafts on the start page. Drafts that
 * cannot be read are left out of the list.
 */
export async function listDrafts(): Promise<DraftSummary[]> {
	const keys = Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index)).filter((key) => key?.startsWith(draftKeyPrefix));

	return keys
		.flatMap((key) => {
			const draft = key ? readStoredDraft(key) : undefined;
			return draft ? [{ id: draft.id, name: draft.name, stage: draft.stage, savedAt: draft.savedAt }] : [];
		})
		.sort((first, second) => second.savedAt.localeCompare(first.savedAt));
}

/**
 * Removes a draft, such as when its form is published. Removing a draft that is not there does nothing, in the same
 * way as deleting a file from a file store.
 */
export async function deleteDraft(id: string): Promise<void> {
	localStorage.removeItem(draftKeyPrefix + id);
}

/**
 * Remembers which draft is open in this browser tab, so the next page opens the same one. It stays in the browser
 * even when drafts are kept on a server, because it belongs to the tab and not to the draft.
 */
export function setOpenDraft(id: string): void {
	sessionStorage.setItem(openDraftKey, id);
}

/**
 * Gives the id of the draft open in this browser tab, or nothing when no draft has been opened or saved in it.
 */
export function readOpenDraft(): string | undefined {
	return sessionStorage.getItem(openDraftKey) ?? undefined;
}
