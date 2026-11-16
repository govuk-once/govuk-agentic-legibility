/*
	The stages shown in the progress banner, from starting something new to publishing it. Each page shows the same
	six stages with a different one current, so the labels are written once here and each list only says how far
	along the page is.
*/

type StageState = 'complete' | 'current' | 'upcoming';

const stageLabels = ['Start', 'Create', 'Edit', 'Tech review', 'Owner check', 'Publish'];

// Builds the six stages with the stage of the given label current, the ones before it complete and the rest upcoming.
function stagesAt(current: string) {
	const at = stageLabels.indexOf(current);
	return stageLabels.map((label, index) => ({
		number: index + 1,
		label,
		state: (index < at ? 'complete' : index === at ? 'current' : 'upcoming') as StageState
	}));
}

// The stages on the start page, where nothing has been made yet.
export const startStages = stagesAt('Start');

// The stages while a service or a form is edited.
export const editStages = stagesAt('Edit');

// The stages while the technical parts of a service or a form are reviewed.
export const techReviewStages = stagesAt('Tech review');
