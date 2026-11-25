import { openFormForReview } from '$lib/form-editor/review-store';
import type { LayoutLoad } from './$types';

// The form sent on from the editor is held in this browser tab, so the pages are built in the browser and never on
// the server, where there is no tab to read it from.
export const ssr = false;

// Every step of the technical review works on the same form, so it is opened once here.
export const load: LayoutLoad = () => ({ workflow: openFormForReview() });
