import { resolve } from '$app/paths';
import type { StageLinks } from '$lib/components/progress-stages';

// Where each stage of the banner goes back to on the form pages. Every form page gives the same addresses, and the
// banner only links the stages that are complete. Create has none, because going back to it would start a new form
// and not return to this one.
export const formStageLinks: StageLinks = {
	Start: resolve('/onboard'),
	Edit: resolve('/edit-form/draft'),
	'Owner review': resolve('/owner-review/form'),
	'Tech review': resolve('/tech-review/form')
};
