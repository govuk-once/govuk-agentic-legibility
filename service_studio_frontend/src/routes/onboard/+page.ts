import { listDrafts } from '$lib/drafts/draft-store';
import type { PageLoad } from './$types';

// The drafts are kept in this browser, so the page is built in the browser and never on the server, where there is no
// browser storage to read them from.
export const ssr = false;

// The saved drafts, and the time they were listed, so every draft's age is worked out from the same moment.
export const load: PageLoad = async () => ({ drafts: await listDrafts(), listedAt: new Date() });
