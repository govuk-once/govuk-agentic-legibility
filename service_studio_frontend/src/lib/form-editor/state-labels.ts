import type { StepOutlineColours } from '$lib/process-graph/process-graph-types';
import type { AnswerDefinition } from '$lib/schema/workflow/input-state';
import type { State } from '$lib/schema/workflow/process';

/*
	The words a person sees for each kind of state in the form editor. The tags on the cards and the panel read
	them from here, so a state is called the same thing wherever it appears. Message is the plain word for output.
	Every other kind keeps the schema's own name, so a developer can match it to the file. Input is one of these,
	because a question in the module menu is made of one or more states and is not the same thing as an input.
*/

// The record is keyed by every kind of state, so adding a kind to the schema without a label here fails to compile.
export const stateLabels: Record<State['state_type'], string> = {
	input: 'Input',
	output: 'Message',
	choice: 'Decision',
	end: 'End',
	assign: 'Assign',
	wait: 'Wait',
	invoke: 'Invoke',
	api_call: 'API call'
};

// The GOV.UK tag colour for each kind of state, so an input, a message and a decision can be told apart at a glance.
// The record is keyed by every kind of state, so adding a kind to the schema without a colour here fails to compile.
export const stateTagColours: Record<State['state_type'], string> = {
	input: 'blue',
	output: 'purple',
	choice: 'yellow',
	assign: 'grey',
	end: 'green',
	wait: 'orange',
	invoke: 'magenta',
	api_call: 'teal'
};

// The colour of the outline of an input box and a message box on the graph, so the two can be told apart there as
// they are by their tags. They are the blue and the purple of the GOV.UK palette. Every other kind of state keeps
// the usual grey outline.
export const stateOutlineColours: StepOutlineColours = {
	input: '#1d70b8',
	output: '#4c2c92'
};

// The words a person sees for each kind of answer an input can take. The record is keyed by every kind of answer,
// so adding a kind to the schema without a label here fails to compile.
export const answerKindLabels: Record<AnswerDefinition['kind'], string> = {
	string: 'Text',
	boolean: 'Yes or no',
	select_one: 'Choose one',
	select_many: 'Choose several',
	file_ref: 'File upload'
};
