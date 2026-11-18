import type { ModuleIconName } from './ModuleIcon.svelte';

/*
	The modules a person can add to a journey, in the order and categories the module menu shows them. A module is a
	ready made set of states, such as a question followed by a decision, so the person picks what they want to happen
	rather than building it from single states. The basic shapes are listed too, for the cases a module does not cover.

	Each module has a key, written in lower case with underscores, which is what is saved in the group metadata of the
	states the module adds. The words on screen come from here and are never read back from the metadata.

	The modules are shared by the form and service editors. Each editor chooses which categories to show.
*/

export interface ModuleTile {
	key: ModuleIconName;
	label: string;
	// A short line saying what the module does, shown in the tooltip under its name.
	description: string;
}

/**
 * Something an editor lets the person drag from the menu onto the canvas, found by the key of its tile. The value is
 * what the canvas reads from the drop: for a step it is the kind of state added, input or output, and for a decision,
 * a start or an end it is the name of the shape. The shape says which of those it is.
 */
export interface PaletteTool {
	module: ModuleIconName;
	value: string;
	shape: 'step' | 'condition' | 'start' | 'end';
}

export interface ModuleCategory {
	label: string;
	modules: ModuleTile[];
}

// The single shapes, for the cases a module does not cover. It is kept apart so an editor can offer only these.
const basics: ModuleCategory = {
	label: 'Basics',
	modules: [
		{ key: 'start', label: 'Start', description: 'Where the journey begins' },
		{ key: 'input', label: 'Input', description: 'A single question' },
		{ key: 'output', label: 'Message', description: 'A single message' },
		{ key: 'decision', label: 'Decision', description: 'Split the journey' },
		{ key: 'end', label: 'End', description: 'Where the journey finishes' }
	]
};

export const moduleCategories: ModuleCategory[] = [
	{
		label: 'Feedback',
		modules: [
			{ key: 'start_page', label: 'Start page', description: 'Information before the journey begins' },
			{ key: 'message', label: 'Message', description: 'Show information' }
		]
	},
	{
		label: 'Ask',
		modules: [
			{ key: 'simple_question', label: 'Simple question', description: 'One typed answer' },
			{ key: 'formatted_question', label: 'Formatted question', description: 'Email, phone, postcode' },
			{ key: 'boolean_question', label: 'Yes/No question', description: 'Ask yes or no' },
			{ key: 'select_one', label: 'Select one', description: 'Ask a question with one option' },
			{ key: 'select_many', label: 'Select many', description: 'Ask a question with many options' },
			{ key: 'many_answers', label: 'Many answers', description: 'One question, several answers' },
			{ key: 'data_question', label: 'Data question', description: 'Ask for an ID number' }
		]
	},
	{
		label: 'Decisions',
		modules: [
			{ key: 'choice_decision', label: 'Choice', description: 'Route by chosen option' },
			{ key: 'boolean_decision', label: 'Yes / No', description: 'Route by yes or no' },
			{ key: 'data_decision', label: 'Data decision', description: 'Route by whether they have it' }
		]
	},
	{
		label: 'Time',
		modules: [
			{ key: 'deadline', label: 'Deadline', description: 'Set a date to act by' },
			{ key: 'wait', label: 'Wait', description: 'Pause the journey' }
		]
	},
	{
		label: 'Flex connections',
		modules: [
			{ key: 'user_details', label: 'User details', description: 'Get details about the user' },
			{ key: 'submit', label: 'Submit', description: 'Send answers to Flex' },
			{ key: 'payment', label: 'Payment', description: 'Take a payment' }
		]
	},
	{
		label: 'Offline',
		modules: [
			{ key: 'information', label: 'Information', description: 'Offline information for citizens' },
			{ key: 'phone_call', label: 'Phone call', description: 'Ring someone' },
			{ key: 'letter', label: 'Letter', description: 'Post a letter' }
		]
	},
	basics
];

// The category of basic shapes, on its own, for an editor that offers only those.
export const basicCategories: ModuleCategory[] = [basics];
