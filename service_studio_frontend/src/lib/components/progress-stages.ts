/*
	The stages shown in the progress banner, from starting something new to signing it off and publishing it. Each page
	shows the same six stages with a different one current, so the labels are written once here and each list only says
	how far along the page is. The owner review comes before the technical review, so the owner can add their details
	while a developer works on the form, and comes back to sign off once it is done.

	A page can give the address of each stage, and a stage that is complete then links back to it. Only complete stages
	link, so a person can go back to work already done but cannot skip ahead past a check. Each kind of page gives its
	own addresses, so this file never needs to know where the form or service pages are.
*/

export type StageState = 'complete' | 'current' | 'upcoming';

export interface Stage {
	number: number;
	label: string;
	state: StageState;
	// Where the stage links to, set only on a complete stage that was given an address.
	href?: string;
}

const stageLabels = ['Start', 'Create', 'Edit', 'Owner review', 'Tech review', 'Sign off'] as const;

export type StageLabel = (typeof stageLabels)[number];

// The address of each stage that can be gone back to, given by the pages of one kind of thing such as a form.
export type StageLinks = Partial<Record<StageLabel, string>>;

/**
 * Builds the six stages with the stage of the given label current, the ones before it complete and the rest
 * upcoming. A complete stage with an address in the links given links back to it.
 */
export function stagesAt(current: StageLabel, links: StageLinks = {}): Stage[] {
	const at = stageLabels.indexOf(current);
	return stageLabels.map((label, index) => {
		const state: StageState = index < at ? 'complete' : index === at ? 'current' : 'upcoming';
		return { number: index + 1, label, state, href: state === 'complete' ? links[label] : undefined };
	});
}

// The stages on the start page, where nothing has been made yet.
export const startStages = stagesAt('Start');

// The stages while a service or a form is edited.
export const editStages = stagesAt('Edit');

// The stages once a service or a form is signed off and published, with every stage complete.
export const publishedStages = stagesAt('Sign off').map((stage) => ({ ...stage, state: 'complete' as const }));
