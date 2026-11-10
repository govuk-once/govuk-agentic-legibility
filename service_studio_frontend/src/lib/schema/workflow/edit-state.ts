import type { WorkingProcess, WorkingState } from './working-process';

/*
	The changes the editor makes to a state, written as plain functions that take a state and return a
	changed copy. Nothing here changes the object it is given, and nothing here checks the result, because
	the whole journey is checked once, before it is passed on, and not after each change.

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
export function descriptionOf(state: WorkingState): string {
	return state.metadata?.[descriptionKey] ?? '';
}

/**
 * Returns a copy of the state with a new title and description. Blank text is trimmed away and the key is
 * removed, and the notes are removed altogether when they end up empty, so a state that has no title or
 * description saves exactly as it would if it never had one.
 */
export function withTitleAndDescription(state: WorkingState, title: string, description: string): WorkingState {
	const updated: WorkingState = { ...state };
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
export function hasText(state: WorkingState): boolean {
	return state.state_type === 'input' || (state.state_type === 'output' && state.channel === 'transcript');
}

/**
 * Returns the words of a state that a person can edit, or an empty string when it has none.
 */
export function textOf(state: WorkingState): string {
	if (state.state_type === 'input') return state.prompt;
	if (state.state_type === 'output' && state.channel === 'transcript') return state.message ?? '';
	return '';
}

/**
 * Returns a copy of the state with new words: the prompt of an input, or the message of a transcript
 * output. A state with no editable words is returned as it is. The text is trimmed, because spaces at
 * either end are never meant to be shown.
 */
export function withText(state: WorkingState, text: string): WorkingState {
	if (state.state_type === 'input') return { ...state, prompt: text.trim() };
	if (state.state_type === 'output' && state.channel === 'transcript') return { ...state, message: text.trim() };
	return state;
}

/**
 * Tells whether a state has a single next state that it continues to. A choice has a rule and a default
 * for each way on instead, and an end has nowhere to go.
 */
export function hasNext(state: WorkingState): state is Exclude<WorkingState, { state_type: 'choice' | 'end' }> {
	return state.state_type !== 'choice' && state.state_type !== 'end';
}

/**
 * Returns a copy of the state that continues to a different state. A state that has no single next state is
 * returned as it is, so a form can call this for every state without checking the type first. The old next
 * state is not touched, so it is left with nothing leading to it if this was its only route.
 */
export function withNext(state: WorkingState, target: string): WorkingState {
	return hasNext(state) ? { ...state, next: target } : state;
}

// The two choices for where a step continues to that are not a state of the process. A choice is a text value
// because it comes from a list in a form. Nothing yet is empty, and a state's name is never empty. The other
// begins and ends with a double underscore, as the start dot's id does, so it cannot be mistaken for a state's name.
export const nothingYet = '';
export const endsTheJourney = '__ends_the_journey__';

/**
 * Returns a copy of the state with the choice made in the form for where it continues to. A state is pointed at,
 * or nothing yet leaves the step with no next. Ending the journey changes nothing here, because making the end
 * adds a state to the process, which only the caller can do.
 */
export function withNextChoice(state: WorkingState, choice: string): WorkingState {
	if (choice === endsTheJourney) return state;
	return choice === nothingYet ? withoutNext(state) : withNext(state, choice);
}

/**
 * Returns a copy of the state with no next state, which leaves it with nothing after it. A state that has no
 * single next state is returned as it is. The state it used to continue to is not touched.
 */
export function withoutNext(state: WorkingState): WorkingState {
	if (!hasNext(state)) return state;

	const { next: _taken, ...rest } = state;
	// The copy has every other key of the same state type. TypeScript cannot see that through the spread.
	return rest as WorkingState;
}

/**
 * Returns a copy of a choice with a new state for each rule to lead to, in the order of its rules, and a new
 * state for its default. The conditions are not changed. Anything that is not a choice is returned as it
 * is. If fewer targets are given than there are rules, the rules without one keep the target they had.
 */
export function withChoiceTargets(state: WorkingState, ruleTargets: string[], defaultTarget: string): WorkingState {
	if (state.state_type !== 'choice') return state;

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
export function replaceState(process: WorkingProcess, code: string, state: WorkingState): WorkingProcess {
	return { ...process, states: { ...process.states, [code]: state } };
}
