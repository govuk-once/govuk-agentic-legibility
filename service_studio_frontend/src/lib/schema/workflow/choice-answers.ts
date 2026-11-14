import type { Condition } from './condition';
import { routesInto } from './edit-process';
import type { InputState } from './input-state';
import type { WorkingProcess, WorkingState } from './working-process';

/*
	How a decision is tied to the answers of the question before it. A decision sends the journey one way or
	another, and in a form it does so on the answer the person has just given. These functions let an editor offer
	that answer as a choice, so a person never has to write a rule.

	1. A decision follows a question when one route leads into it and that route is the next of an input state. A
	   decision that something else leads to, or that several states lead to, follows no single question.
	2. Only a question with a fixed list of answers can be offered: yes or no, and choose one. A question that is
	   answered by typing has no list of answers, so nothing is offered for it.
	3. Yes is written as is_true on the variable the answer is saved in, no as is_false, and an option as eq with
	   the value of the option.
*/

// One answer a person can give to a question: the value it is told apart by, and the words shown for it.
export type AnswerChoice = { value: string; label: string };

// The two answers to a yes or no question. The values are only used to tell the two apart in a list of choices.
export const yesAnswer = 'yes';
export const noAnswer = 'no';
const yesOrNoChoices: AnswerChoice[] = [
	{ value: yesAnswer, label: 'Yes' },
	{ value: noAnswer, label: 'No' }
];

// An input as the editor holds it, which may not continue anywhere yet.
type WorkingInput = Extract<WorkingState, { state_type: 'input' }>;

/**
 * Finds the question a decision follows, with its code. There is none when the state is not reached by exactly
 * one route, when that route is not the next of a question, or when the decision is the start of the process.
 */
export function questionBefore(process: WorkingProcess, choiceCode: string): { code: string; question: WorkingInput } | undefined {
	const into = routesInto(process, choiceCode);
	if (into.length !== 1 || into[0].route.kind !== 'next' || process.start === choiceCode) return undefined;

	const question = process.states[into[0].source];
	return question?.state_type === 'input' ? { code: into[0].source, question } : undefined;
}

/**
 * Lists the answers a question offers, for a list of choices. A yes or no question offers yes and no. A choose
 * one question offers its options, when they are written out in the question. Every other kind of question
 * offers none, because its answer is not one of a fixed list.
 */
export function answerChoices(question: Pick<InputState, 'schema'>): AnswerChoice[] {
	const { schema } = question;
	if (schema.kind === 'boolean') return yesOrNoChoices;
	if (schema.kind === 'select_one') return schema.options ?? [];
	return [];
}

/**
 * Writes the rule that is true when a question was given one of its answers. Returns nothing when the answer is
 * not one the question offers, so a rule is never written for an answer that cannot be given.
 */
export function conditionForAnswer(question: Pick<InputState, 'schema' | 'assign'>, answer: string): Condition | undefined {
	if (!answerChoices(question).some((choice) => choice.value === answer)) return undefined;

	if (question.schema.kind === 'boolean') {
		return { op: answer === yesAnswer ? 'is_true' : 'is_false', path: question.assign };
	}
	return { op: 'eq', path: question.assign, value: answer };
}

/**
 * Reads which answer of a question a rule is for, which is the opposite of conditionForAnswer. Returns nothing
 * when the rule tests something else, such as another variable, or is not a test this file writes, so an editor
 * can show such a rule as it is and not offer to change it.
 */
export function answerOfCondition(question: Pick<InputState, 'schema' | 'assign'>, condition: Condition): string | undefined {
	return answerChoices(question).find((choice) => {
		const written = conditionForAnswer(question, choice.value);
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
