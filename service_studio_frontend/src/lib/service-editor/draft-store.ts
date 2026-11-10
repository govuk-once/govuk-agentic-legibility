import { createDraftStore } from '$lib/draft-store';

// The name the service draft is kept under, so the form editor can keep its own draft beside it.
export const { saveDraft, loadDraft } = createDraftStore('service-studio.service-draft');
