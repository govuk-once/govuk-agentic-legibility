/*
	The stages shown in the progress banner, from starting something new to signing it off and publishing it. Each page
	shows the same six stages with a different one current, so the labels are written once here and each list only says
	how far along the page is. The owner review comes before the technical review, so the owner can add their details
	while a developer works on the form, and comes back to sign off once it is done.
*/

// An unfinished stage is one that comes before the current stage but has not been finished, so the banner can
// warn that the page was reached early.
export type StageState = 'complete' | 'unfinished' | 'current' | 'upcoming';

export interface Stage {
	number: number;
	label: string;
	state: StageState;
}

const stageLabels = ['Start', 'Create', 'Edit', 'Owner review', 'Tech review', 'Sign off'];

/**
 * Builds the six stages with the stage of the given label current, the ones before it complete and the rest
 * upcoming. An earlier stage named in unfinished is shown as not finished in place of complete.
 */
export function stagesAt(current: string, unfinished: string[] = []): Stage[] {
	const at = stageLabels.indexOf(current);
	return stageLabels.map((label, index) => {
		if (index < at && unfinished.includes(label)) return { number: index + 1, label: `${label} not finished`, state: 'unfinished' };
		const state: StageState = index < at ? 'complete' : index === at ? 'current' : 'upcoming';
		return { number: index + 1, label, state };
	});
}

// The stages on the start page, where nothing has been made yet.
export const startStages = stagesAt('Start');

// The stages while a service or a form is edited.
export const editStages = stagesAt('Edit');

// The stages while the technical parts of a service or a form are reviewed.
export const techReviewStages = stagesAt('Tech review');

// The stages once a service or a form is signed off and published, with every stage complete.
export const publishedStages = stagesAt('Sign off').map((stage) => ({ ...stage, state: 'complete' as const }));
