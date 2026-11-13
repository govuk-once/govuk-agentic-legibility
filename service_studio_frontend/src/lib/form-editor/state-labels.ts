import type { State } from '$lib/schema/workflow/process';

/*
	The words a person sees for each kind of state in the form editor. The palette and the tags on the cards both read
	them from here, so a state is called the same thing wherever it appears. Question and Message are the plain words
	for input and output. The other kinds keep the schema's own names, so a developer can match them to the file.
*/

// The record is keyed by every kind of state, so adding a kind to the schema without a label here fails to compile.
export const stateLabels: Record<State['state_type'], string> = {
	input: 'Question',
	output: 'Message',
	choice: 'Decision',
	end: 'End',
	assign: 'Assign',
	wait: 'Wait',
	invoke: 'Invoke',
	api_call: 'API call'
};

// The start dot is on the canvas but is not a state of the process, so it has a label of its own.
export const startLabel = 'Start';
