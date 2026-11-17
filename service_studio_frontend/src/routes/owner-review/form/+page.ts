import { loadFormForReview } from '$lib/form-editor/review-store';
import { checkLoadedForm } from '$lib/form-editor/schema/form-states';
import type { PageLoad } from './$types';

// The form sent on from the editor is held in this browser tab, so the page is built in the browser and never on the
// server, where there is no tab to read it from.
export const ssr = false;

export const load: PageLoad = () => ({ form: checkLoadedForm(loadFormForReview()) });
