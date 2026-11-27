import type { AnswerChoice } from '$lib/schema/frontend/choice-answers';
import type { WorkingState } from '$lib/schema/frontend/working-process';

/*
	The options of an input where the person chooses one or several answers, as an editor changes them.

	1. The value of an option is made once, when the option is added, and never changes. Only the label is typed by
	   the person. A decision tests the value, so it keeps working while the words of the option are edited.
	2. A new option is given the value option_ and a number that no other option of the input has, so a value that
	   belonged to a removed option is never given to a different option.
*/

/**
 * Lists the options of an input that the person can change here, which are the options written out in the input.
 * An input that reads its options from a variable, or is not a choice, has none to change.
 */
export function editableOptions(state: WorkingState): AnswerChoice[] | undefined {
	if (state.state_type !== 'input') return undefined;
	const { schema } = state;
	return (schema.kind === 'select_one' || schema.kind === 'select_many') && schema.options ? schema.options : undefined;
}

/**
 * Makes a new option to add after the given ones, with a placeholder label and a value that none of them has.
 */
export function newOption(options: AnswerChoice[]): AnswerChoice {
	const taken = new Set(options.map((option) => option.value));
	let number = options.length + 1;
	while (taken.has(`option_${number}`)) number += 1;
	return { value: `option_${number}`, label: `Option ${number}` };
}

/**
 * Gives an input the options it is given, with the spaces around each label removed. A state that has no options
 * to change is returned as it is.
 */
export function withOptions(state: WorkingState, options: AnswerChoice[]): WorkingState {
	if (state.state_type !== 'input') return state;
	const { schema } = state;
	if ((schema.kind !== 'select_one' && schema.kind !== 'select_many') || !schema.options) return state;
	const tidied = options.map((option) => ({ value: option.value, label: option.label.trim() }));
	return { ...state, schema: { ...schema, options: tidied } };
}
