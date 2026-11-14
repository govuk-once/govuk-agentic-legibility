import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import { answerChoices, answerOfCondition, conditionForAnswer, noAnswer, questionBefore, yesAnswer } from '../choice-answers';
import type { Condition } from '../condition';
import type { InputState } from '../input-state';
import type { Process } from '../process';

const finish = { state_type: 'end', status: 'success' };
const rule = (next: string, when: unknown = { op: 'is_true', path: 'ok' }) => ({ when, next });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

// A question with only the keys the functions read.
const question = (schema: unknown, assign = 'answer') => ({ schema, assign }) as Pick<InputState, 'schema' | 'assign'>;

const yesOrNo = question({ kind: 'boolean' }, 'ok');
const chooseOne = question({ kind: 'select_one', options: [{ value: 'post', label: 'By post' }, { value: 'online', label: 'Online' }] }, 'method');

describe('questionBefore', () => {
	const ask = { state_type: 'input', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'decide' };
	const decide = { state_type: 'choice', rules: [rule('yes')], default: 'no' };

	it('finds the question whose next is the decision', () => {
		const found = questionBefore(build('ask', { ask, decide, yes: finish, no: finish }), 'decide');
		expect(found?.code).toBe('ask');
		expect(found?.question.assign).toBe('ok');
	});

	it('finds none when a message leads to the decision', () => {
		const say = { state_type: 'output', channel: 'transcript', message: 'Hello', next: 'decide' };
		expect(questionBefore(build('say', { say, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when two states lead to the decision, or none does', () => {
		const other = { ...ask, next: 'decide' };
		expect(questionBefore(build('ask', { ask, other, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
		expect(questionBefore(build('ask', { ask: { ...ask, next: 'yes' }, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when the question only leads to the decision by a route for an invalid answer', () => {
		const invalid = { ...ask, next: 'yes', on_invalid: 'decide' };
		expect(questionBefore(build('ask', { ask: invalid, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when the decision is the start of the process', () => {
		expect(questionBefore(build('decide', { ask, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});
});

describe('answerChoices', () => {
	it('offers yes and no for a yes or no question', () => {
		expect(answerChoices(yesOrNo)).toEqual([
			{ value: yesAnswer, label: 'Yes' },
			{ value: noAnswer, label: 'No' }
		]);
	});

	it('offers the options of a choose one question', () => {
		expect(answerChoices(chooseOne).map((choice) => choice.label)).toEqual(['By post', 'Online']);
	});

	it('offers nothing for a question answered by typing, by a file, by choosing several, or with options read at run time', () => {
		expect(answerChoices(question({ kind: 'string' }))).toEqual([]);
		expect(answerChoices(question({ kind: 'file_ref' }))).toEqual([]);
		expect(answerChoices(question({ kind: 'select_many', options: [{ value: 'a', label: 'A' }] }))).toEqual([]);
		expect(answerChoices(question({ kind: 'select_one', options_from: 'list' }))).toEqual([]);
	});
});

describe('conditionForAnswer and answerOfCondition', () => {
	it('writes yes as is_true and no as is_false on the variable the answer is saved in', () => {
		expect(conditionForAnswer(yesOrNo, yesAnswer)).toEqual({ op: 'is_true', path: 'ok' });
		expect(conditionForAnswer(yesOrNo, noAnswer)).toEqual({ op: 'is_false', path: 'ok' });
	});

	it('writes an option as eq with the value of the option', () => {
		expect(conditionForAnswer(chooseOne, 'post')).toEqual({ op: 'eq', path: 'method', value: 'post' });
	});

	it('writes nothing for an answer the question does not offer', () => {
		expect(conditionForAnswer(chooseOne, 'by_phone')).toBeUndefined();
		expect(conditionForAnswer(question({ kind: 'string' }), 'anything')).toBeUndefined();
	});

	it('reads back the answer of every rule it writes', () => {
		for (const [asked, answers] of [[yesOrNo, [yesAnswer, noAnswer]], [chooseOne, ['post', 'online']]] as const) {
			for (const answer of answers) expect(answerOfCondition(asked, conditionForAnswer(asked, answer)!)).toBe(answer);
		}
	});

	it('reads nothing from a rule about another variable, another value, or another kind of test', () => {
		const conditions: Condition[] = [
			{ op: 'is_true', path: 'something_else' },
			{ op: 'not_empty', path: 'ok' },
			{ op: 'and', all: [{ op: 'is_true', path: 'ok' }] },
			{ op: 'eq', path: 'ok', value: true }
		];
		for (const condition of conditions) expect(answerOfCondition(yesOrNo, condition), JSON.stringify(condition)).toBeUndefined();

		expect(answerOfCondition(chooseOne, { op: 'eq', path: 'method', value: 'by_phone' })).toBeUndefined();
		expect(answerOfCondition(chooseOne, { op: 'eq', path: 'method', value_path: 'other' })).toBeUndefined();
	});
});

describe('the decisions in the form examples', () => {
	// Every rule of every decision, with the question the decision follows.
	const rules = formExamples.flatMap((example) =>
		Object.values(example.workflow?.processes ?? {}).flatMap((process) =>
			Object.entries(process.states).flatMap(([code, state]) =>
				state.state_type === 'choice' ? state.rules.map((each) => ({ slug: example.slug, code, when: each.when, before: questionBefore(process, code) })) : []
			)
		)
	);

	it('all follow a single question', () => {
		expect(rules).toHaveLength(44);
		for (const each of rules) expect(each.before, `${each.slug}: ${each.code}`).toBeDefined();
	});

	it('are read as an answer of that question, and written back exactly, when it is yes or no or choose one', () => {
		const offered = rules.filter((each) => answerChoices(each.before!.question).length > 0);
		expect(offered).toHaveLength(43);

		for (const each of offered) {
			const answer = answerOfCondition(each.before!.question, each.when);
			expect(answer, `${each.slug}: ${each.code}`).toBeDefined();
			expect(conditionForAnswer(each.before!.question, answer!)).toEqual(each.when);
		}
	});

	it('leave one rule that is not offered, which follows a choose several question', () => {
		const notOffered = rules.filter((each) => answerChoices(each.before!.question).length === 0);
		expect(notOffered.map((each) => each.before!.question.schema.kind)).toEqual(['select_many']);
	});
});
