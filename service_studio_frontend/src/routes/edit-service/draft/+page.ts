import { loadDraft } from '$lib/service-editor/draft-store';
import type { PageLoad } from './$types';

// The draft is held in this browser tab, so the page is built in the browser and never on the server, where there is
// no tab to read it from.
export const ssr = false;

export const load: PageLoad = () => ({ draft: loadDraft() });
