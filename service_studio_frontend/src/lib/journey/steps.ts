import type { BranchDecoration } from '$lib/graph/types';
import type { JourneyStep } from './types';

// The starting steps for the address change example journey. This stands in for the real schema, which
// this file will be replaced by once it exists.
export const initialSteps: JourneyStep[] = [
	{
		id: 'step-1',
		title: 'Choose how to enter your address',
		description: 'Required: user must follow step 2 or 3',
		tagLabel: 'Address',
		tagColour: 'blue',
		answerType: 'question-group',
		branchesTo: 'step-2'
	},
	{
		id: 'step-2',
		title: 'Find address by postcode',
		description: 'Optional: postcode lookup',
		tagLabel: 'Address',
		tagColour: 'blue',
		answerType: 'question-group',
		branchesTo: null
	},
	{
		id: 'step-3',
		title: 'Enter address manually',
		description: 'Optional: address form',
		tagLabel: 'Address',
		tagColour: 'blue',
		answerType: 'question-group',
		branchesTo: null
	},
	{
		id: 'step-4',
		title: 'Confirm your new address',
		description: 'Required: confirms the update succeeded',
		tagLabel: 'Confirm',
		tagColour: 'blue',
		answerType: 'declaration',
		branchesTo: null
	}
];

// Describes the one branch point in this example journey: after the first step, the user's choice of
// entry method sends them down whichever two steps currently sit second and third, and both paths rejoin
// at whichever step follows those.
export const addressChangeBranchDecoration: BranchDecoration = {
	afterIndex: 0,
	question: 'Postcode or manual entry?',
	branchLabels: [
		{ label: 'Postcode', tagColour: 'grey' },
		{ label: 'Manual', tagColour: 'grey' }
	]
};
