import type { StepOutlineColours } from '$lib/process-graph/process-graph-types';
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

// The GOV.UK tag colour for each kind of state, so a question, a message and a decision can be told apart at a glance.
// The record is keyed by every kind of state, so adding a kind to the schema without a colour here fails to compile.
export const stateTagColours: Record<State['state_type'], string> = {
	input: 'blue',
	output: 'purple',
	choice: 'yellow',
	assign: 'grey',
	end: 'green',
	wait: 'orange',
	invoke: 'teal',
	api_call: 'magenta'
};

// The colour of the outline of a question box and a message box on the graph, so the two can be told apart there as
// they are by their tags. They are the blue and the purple of the GOV.UK palette. Every other kind of state keeps
// the usual grey outline.
export const stateOutlineColours: StepOutlineColours = {
	input: '#1d70b8',
	output: '#4c2c92'
};
