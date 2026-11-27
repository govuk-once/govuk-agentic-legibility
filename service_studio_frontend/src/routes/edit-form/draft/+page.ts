import type { DraftLoad } from '$lib/drafts/draft-load';
import { openDraft, readOpenDraft, type SavedDraft } from '$lib/drafts/draft-store';
import type { PageLoad } from './$types';

// The draft is kept in this browser, so the page is built in the browser and never on the server, where there is no
// browser storage to read it from.
export const ssr = false;

// The draft the editor opens, or why it could not, in the shape the problem page reads.
type EditorDraft = { ok: true; draft: SavedDraft } | Extract<DraftLoad, { ok: false }>;

// Opens the draft that is open in this browser tab. Its form is not checked against the schema, because a draft may be
// saved while the journey is unfinished. A draft that cannot be read is given an issue, so the problem page can say so.
export const load: PageLoad = async (): Promise<{ opened: EditorDraft }> => {
	const id = readOpenDraft();
	const opened = id ? await openDraft(id) : undefined;

	if (opened?.ok) return { opened };
	if (opened?.reason === 'unreadable') {
		return { opened: { ok: false, reason: 'invalid', issues: [{ path: '(root)', message: 'The saved draft could not be read.' }] } };
	}
	return { opened: { ok: false, reason: 'missing' } };
};
