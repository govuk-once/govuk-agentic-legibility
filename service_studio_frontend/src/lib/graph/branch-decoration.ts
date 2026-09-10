import type { BranchDecoration } from './types';

// Describes the one branch point in the address change example journey: after the first step, the user's
// choice of entry method sends them down whichever two steps currently sit second and third, and both
// paths rejoin at whichever step follows those. Kept here with the rest of the graph editor, rather than
// beside the step data, so the step list stays pure journey content with no dependency on the graph.
export const addressChangeBranchDecoration: BranchDecoration = {
	afterIndex: 0,
	question: 'Postcode or manual entry?',
	branchLabels: [
		{ label: 'Postcode', tagColour: 'grey' },
		{ label: 'Manual', tagColour: 'grey' }
	]
};
