import type { Process, State } from './process';

/*
	The changes the editor makes to a state, written as plain functions that take a state and return a
	changed copy. Nothing here changes the object it is given, and nothing here checks the result, because
	the page checks the whole workflow after every change.

	1. The title of a state is its name. The description is kept in the notes of the state, which are its
	   metadata, under the key description. The executor team have agreed that the notes only carry text.
	2. A blank title or description removes the key instead of saving an empty value, because the schema
	   does not accept an empty name and an empty note would only add clutter to the saved file.
*/

// The key in a state's notes that holds its description.
export const descriptionKey = 'description';

/**
 * Returns the description of a state, or an empty string when it has none, so a form can show it without
 * checking that the notes exist.
 */
export function descriptionOf(state: State): string {
	return state.metadata?.[descriptionKey] ?? '';
}

/**
 * Returns a copy of the state with a new title and description. Blank text is trimmed away and the key is
 * removed, and the notes are removed altogether when they end up empty, so a state that has no title or
 * description saves exactly as it would if it never had one.
 */
export function withTitleAndDescription(state: State, title: string, description: string): State {
	const updated: State = { ...state };
	const notes = { ...state.metadata };

	if (title.trim()) updated.name = title.trim();
	else delete updated.name;

	if (description.trim()) notes[descriptionKey] = description.trim();
	else delete notes[descriptionKey];

	if (Object.keys(notes).length > 0) updated.metadata = notes;
	else delete updated.metadata;

	return updated;
}

/**
 * Tells whether a state has words of its own that a person can edit: the question an input asks, or the
 * message a transcript output shows. An email or sms output holds only the name of a template, and the
 * wording of the template is kept in another system, so there is no text here to edit for it.
 */
export function hasText(state: State): boolean {
	return state.type === 'input' || (state.type === 'output' && state.channel === 'transcript');
}

/**
 * Returns the words of a state that a person can edit, or an empty string when it has none.
 */
export function textOf(state: State): string {
	if (state.type === 'input') return state.prompt;
	if (state.type === 'output' && state.channel === 'transcript') return state.message ?? '';
	return '';
}

/**
 * Returns a copy of the state with new words: the prompt of an input, or the message of a transcript
 * output. A state with no editable words is returned as it is. The text is trimmed, because spaces at
 * either end are never meant to be shown.
 */
export function withText(state: State, text: string): State {
	if (state.type === 'input') return { ...state, prompt: text.trim() };
	if (state.type === 'output' && state.channel === 'transcript') return { ...state, message: text.trim() };
	return state;
}

/**
 * Tells whether a state has a single next state that it continues to. A choice has a rule and a default
 * for each way on instead, and an end has nowhere to go.
 */
export function hasNext(state: State): state is Exclude<State, { type: 'choice' | 'end' }> {
	return state.type !== 'choice' && state.type !== 'end';
}

/**
 * Returns a copy of the state that continues to a different state. A state that has no single next state is
 * returned as it is, so a form can call this for every state without checking the type first. The old next
 * state is not touched, so it is left with nothing leading to it if this was its only route.
 */
export function withNext(state: State, target: string): State {
	return hasNext(state) ? { ...state, next: target } : state;
}

/**
 * Returns a copy of a choice with a new state for each rule to lead to, in the order of its rules, and a new
 * state for its default. The conditions are not changed. Anything that is not a choice is returned as it
 * is. If fewer targets are given than there are rules, the rules without one keep the target they had.
 */
export function withChoiceTargets(state: State, ruleTargets: string[], defaultTarget: string): State {
	if (state.type !== 'choice') return state;

	return {
		...state,
		rules: state.rules.map((rule, index) => ({ ...rule, next: ruleTargets[index] ?? rule.next })),
		default: defaultTarget
	};
}

/**
 * Returns a copy of the process with one state replaced. The other states are the same objects as before,
 * so a large process is not copied in full for a small change.
 */
export function replaceState(process: Process, code: string, state: State): Process {
	return { ...process, states: { ...process.states, [code]: state } };
}
