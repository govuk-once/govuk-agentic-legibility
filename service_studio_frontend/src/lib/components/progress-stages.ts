/*
	The stages shown in the progress banner, from starting something new to signing it off and publishing it. Each page
	shows the same six stages with a different one current, so the labels are written once here and each list only says
	how far along the page is. The owner review comes before the technical review, so the owner can add their details
	while a developer works on the form, and comes back to sign off once it is done.
*/

export type StageState = 'complete' | 'current' | 'upcoming';

export interface Stage {
	number: number;
	label: string;
	state: StageState;
}

const stageLabels = ['Start', 'Create', 'Edit', 'Owner review', 'Tech review', 'Sign off'];

/**
 * Builds the six stages with the stage of the given label current, the ones before it complete and the rest
 * upcoming.
 */
export function stagesAt(current: string): Stage[] {
	const at = stageLabels.indexOf(current);
	return stageLabels.map((label, index) => {
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
