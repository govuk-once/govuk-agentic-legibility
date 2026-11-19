import { createDraftStore } from '$lib/draft-store';

// The name the form draft is kept under, so it never mixes with a service draft in the same tab.
export const { saveDraft, loadDraft } = createDraftStore('service-studio.form-draft');
