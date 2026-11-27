import type { Condition } from '$lib/schema/workflow/condition';
import { routesInto } from '$lib/schema/workflow/edit-process';
import type { InputState } from '$lib/schema/workflow/input-state';
import type { WorkingInput, WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';

/*
	How a decision is tied to the answers of the input before it. A decision sends the journey one way or
	another, and in a form it does so on the answer the person has just given. These functions let an editor offer
	that answer as a choice, so a person never has to write a rule.

	1. A decision follows an input when one route leads into it and that route is the next of the input. A
	   decision that something else leads to, or that several states lead to, follows no single input.
	2. Only an input with a fixed list of answers has answers to name: yes or no, choose one and choose several.
	   An input that is answered by typing has no list of answers, so it has none.
	3. Yes is written as is_true on the variable the answer is saved in, no as is_false, and an option as eq with
	   the value of the option, which is how the form files write them.
*/

// One answer a person can give to an input: the value it is told apart by, and the words shown for it.
export type AnswerChoice = { value: string; label: string };

// The two answers to a yes or no input. The values are only used to tell the two apart in a list of choices.
const yesAnswer = 'yes';
const noAnswer = 'no';
const yesOrNoChoices: AnswerChoice[] = [
	{ value: yesAnswer, label: 'Yes' },
	{ value: noAnswer, label: 'No' }
];

/**
 * Finds the state a decision follows, with its code. There is none when the decision is not reached by exactly one
 * route, when that route is not the next of a state, or when the decision is the start of the process.
 */
export function stateBefore(process: WorkingProcess, choiceCode: string): { code: string; state: WorkingState } | undefined {
	const into = routesInto(process, choiceCode);
	if (into.length !== 1 || into[0].route.kind !== 'next' || process.start === choiceCode) return undefined;

	const state = process.states[into[0].source];
	return state ? { code: into[0].source, state } : undefined;
}

/**
 * Finds the input a decision follows, with its code. There is none when the decision follows no single state, or
 * the state it follows is not an input.
 */
export function inputBefore(process: WorkingProcess, choiceCode: string): { code: string; input: WorkingInput } | undefined {
	const before = stateBefore(process, choiceCode);
	return before?.state.state_type === 'input' ? { code: before.code, input: before.state } : undefined;
}

/**
 * Lists the answers an input offers. A yes or no input offers yes and no. An input where the person chooses
 * one or several offers its options, when they are written out in the input. Every other kind of input offers
 * none, because its answer is not one of a fixed list.
 */
export function answerChoices(input: Pick<InputState, 'schema'>): AnswerChoice[] {
	const { schema } = input;
	if (schema.kind === 'boolean') return yesOrNoChoices;
	if (schema.kind === 'select_one' || schema.kind === 'select_many') return schema.options ?? [];
	return [];
}

/**
 * Writes the rule that is true when an input was given one of its answers. Returns nothing when the answer is
 * not one the input offers, so a rule is never written for an answer that cannot be given.
 */
export function conditionForAnswer(input: Pick<InputState, 'schema' | 'assign'>, answer: string): Condition | undefined {
	if (!answerChoices(input).some((choice) => choice.value === answer)) return undefined;

	if (input.schema.kind === 'boolean') {
		return { op: answer === yesAnswer ? 'is_true' : 'is_false', path: input.assign };
	}
	return { op: 'eq', path: input.assign, value: answer };
}

/**
 * Reads which answer of an input a rule is for, which is the opposite of conditionForAnswer. Returns nothing
 * when the rule tests something else, such as another variable, or is not a test this file writes, so an editor
 * can show such a rule as it is and not offer to change it.
 */
export function answerOfCondition(input: Pick<InputState, 'schema' | 'assign'>, condition: Condition): string | undefined {
	return answerChoices(input).find((choice) => {
		const written = conditionForAnswer(input, choice.value);
		return (
			written !== undefined &&
			written.op === condition.op &&
			'path' in condition &&
			'path' in written &&
			written.path === condition.path &&
			('value' in written ? 'value' in condition && written.value === condition.value : !('value' in condition) && !('value_path' in condition))
		);
	})?.value;
}
