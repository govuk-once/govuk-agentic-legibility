import { openDraftForReview } from '$lib/form-editor/review-draft';
import type { LayoutLoad } from './$types';

// The draft is kept in this browser, so the pages are built in the browser and never on the server, where there is no
// browser storage to read it from.
export const ssr = false;

// Every step of the technical review works on the same form, so it is opened once here.
export const load: LayoutLoad = () => openDraftForReview();
