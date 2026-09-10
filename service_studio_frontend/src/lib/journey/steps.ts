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
