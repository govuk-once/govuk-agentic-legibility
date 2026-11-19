import { loadDraft } from '$lib/form-editor/draft-store';
import { checkLoadedForm } from '$lib/form-editor/schema/form-states';
import type { PageLoad } from './$types';

// The draft is held in this browser tab, so the page is built in the browser and never on the server, where there is
// no tab to read it from.
export const ssr = false;

// The form editor opens only one process, so the draft is checked to be a single process as well as matching the schema.
export const load: PageLoad = () => ({ draft: checkLoadedForm(loadDraft()) });
