import type { DraftLoad } from '$lib/draft-store';
import { loadDraft } from '$lib/form-editor/draft-store';
import { checkFormWorkflow } from '$lib/form-editor/schema/form-states';
import type { PageLoad } from './$types';

// The draft is held in this browser tab, so the page is built in the browser and never on the server, where there is
// no tab to read it from.
export const ssr = false;

// A draft that matches the schema is also checked to be a single process, as the examples are, because the form
// editor opens only one process. A draft that is not is shown with the problem, in the same way as one that does not
// match the schema.
export const load: PageLoad = () => {
	const loaded = loadDraft();
	if (!loaded.ok) return { draft: loaded };

	const issues = checkFormWorkflow(loaded.workflow);
	const draft: DraftLoad = issues.length > 0 ? { ok: false, reason: 'invalid', issues } : loaded;
	return { draft };
};
