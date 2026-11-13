import { apiCallStateSchema } from '$lib/schema/workflow/api-call-state';
import { inputStateSchema } from '$lib/schema/workflow/input-state';
import { textOf } from '$lib/schema/workflow/edit-state';
import {
	placeholderAnswerKind,
	placeholderAnswerVariable,
	placeholderMessage,
	placeholderQuestion,
	placeholderWaitDuration,
	unconnectedApiCallDetails
} from '$lib/schema/workflow/placeholders';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import { assignStateSchema, outputStateSchema, waitStateSchema } from '$lib/schema/workflow/states';

/*
	Changing a step from one type to another, for example an input to an output. Only the types that
	continue to one next state can be changed this way. A decision is a diamond and an end is a dot, and
	each of those has routes of its own, so they stay what they are.

	1. Every key the old and the new type both have is kept. That covers the name, the notes, the next
	   state and any key with the same meaning in both, such as where a result is saved. A key only the old
	   type has is removed, and the person is told first.
	2. The words of an input or a transcript output are carried over to the other, so the question becomes
	   the message and the message becomes the question.
	3. A key the new type needs and the old one cannot supply is filled with a placeholder, so the result is
	   valid at once and the person completes it afterwards.
	4. An invoke state can be changed into another type but nothing can be changed into one, because it
	   needs the name of a process to run and there is no sensible one to guess.
*/

/**
 * The types a step can be changed into, in the order a list of choices shows them. Invoke is not one of
 * them, because it needs the name of a process to run.
 */
export const convertTargetTypes = ['input', 'output', 'api_call', 'assign', 'wait'] as const;

export type ConvertTargetType = (typeof convertTargetTypes)[number];

// Every type a step can be changed from, which is the targets and invoke.
export type ConvertibleType = ConvertTargetType | 'invoke';

/**
 * Tells whether some text is the name of a type that a step can be changed into. A form holds the chosen
 * type as text, and this says whether it is one that convertState accepts.
 */
export function isConvertTargetType(type: string): type is ConvertTargetType {
	return (convertTargetTypes as readonly string[]).includes(type);
}

// The keys each type is allowed to have, taken from its schema so this list can never drift away from it.
const keysOfType: Record<ConvertTargetType, ReadonlySet<string>> = {
	input: new Set(Object.keys(inputStateSchema.shape)),
	output: new Set(Object.keys(outputStateSchema.shape)),
	api_call: new Set(Object.keys(apiCallStateSchema.shape)),
	assign: new Set(Object.keys(assignStateSchema.shape)),
	wait: new Set(Object.keys(waitStateSchema.shape))
};

// The keys that every type shares or that the conversion handles itself, so they are never reported as lost.
const alwaysKept = new Set(['state_type', 'name', 'metadata', 'next']);

// Plain words for each key, used when telling the person what a change will remove. Several keys can
// share a name, such as the three that make up a request, and the name is only shown once.
const keyNames: Record<string, string> = {
	prompt: 'the question',
	schema: 'the answer type',
	assign: 'where the answer is saved',
	on_invalid: 'the route for an invalid answer',
	timeout: 'the timeout',
	channel: 'the channel',
	message: 'the message',
	template: 'the template',
	params: 'the template values',
	idempotency_key: 'the idempotency key',
	also_transcript: 'the copy in the transcript',
	on_error: 'what happens when sending fails',
	method: 'the request',
	service: 'the request',
	url: 'the request',
	headers: 'the headers',
	body: 'the request body',
	source_ref: 'the file to upload',
	encoding: 'the encoding',
	timeouts: 'the timeouts',
	retry: 'the retry settings',
	capture: 'the values kept from the response',
	catch: 'the routes for errors',
	set: 'the values it sets',
	process: 'the process it runs',
	input: 'the values passed in',
	duration: 'how long it waits'
};

/**
 * Tells whether a state can be changed into another type. A decision and an end cannot, because each has
 * routes that the other types do not.
 */
export function isConvertible(state: WorkingState): state is Extract<WorkingState, { state_type: ConvertibleType }> {
	return state.state_type !== 'choice' && state.state_type !== 'end';
}

/**
 * Lists, in plain words, what is removed from a state when it is changed to another type. The words of an
 * input or a transcript output are carried over to the other, so they are not counted as lost. An empty
 * list means nothing is lost, which is also the answer when the type does not change.
 */
export function lostByConversion(state: WorkingState, toType: ConvertTargetType): string[] {
	if (!isConvertible(state) || state.state_type === toType) return [];

	const carriesText = textOf(state) !== '' && (toType === 'input' || toType === 'output');
	const lost = Object.keys(state)
		.filter((key) => !alwaysKept.has(key) && !keysOfType[toType].has(key))
		.filter((key) => !(carriesText && (key === 'prompt' || key === 'message')))
		.map((key) => keyNames[key] ?? key);

	return [...new Set(lost)];
}

/**
 * Returns a copy of the state changed to another type. The keys both types have are kept, the words are
 * carried across, and any key the new type needs is filled with a placeholder. The code of the state is
 * used to name the variable of a new input. A state that cannot be changed, or is already the type asked
 * for, is returned as it is.
 */
export function convertState(state: WorkingState, toType: ConvertTargetType, stateCode: string): WorkingState {
	if (!isConvertible(state) || state.state_type === toType) return state;

	const kept = Object.fromEntries(Object.entries(state).filter(([key]) => key !== 'state_type' && keysOfType[toType].has(key)));
	const words = textOf(state);

	const placeholders: Record<ConvertTargetType, Record<string, unknown>> = {
		input: {
			prompt: words || placeholderQuestion,
			schema: { kind: placeholderAnswerKind },
			assign: placeholderAnswerVariable(stateCode)
		},
		output: { channel: 'transcript', message: words || placeholderMessage },
		api_call: { ...unconnectedApiCallDetails },
		assign: { set: {} },
		wait: { duration: placeholderWaitDuration }
	};

	// The result is built from keys and not from a typed object, because the keys depend on the types chosen.
	// The result is not checked here. The whole journey is checked once, before it is passed on.
	return { ...placeholders[toType], ...kept, state_type: toType } as WorkingState;
}
