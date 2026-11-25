import { openDraftForReview } from '$lib/form-editor/review-draft';
import type { LayoutLoad } from './$types';

// Every step of the owner review works on the same form, so it is opened once here. The page after publishing sits
// outside this group, because the draft is deleted when the form is published.
export const load: LayoutLoad = () => openDraftForReview();
