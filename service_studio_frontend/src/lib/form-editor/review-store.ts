import { createDraftStore } from '$lib/draft-store';

// The edited form, held in the browser tab when it is sent to tech review so the review pages after the editor can
// open it. It has its own key, so sending a form on never replaces a generated draft that has not been opened yet.
export const { saveDraft: saveFormForReview, loadDraft: loadFormForReview } = createDraftStore('service-studio.form-review');
