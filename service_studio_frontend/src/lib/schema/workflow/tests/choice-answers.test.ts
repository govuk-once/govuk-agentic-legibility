import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import { answerChoices, answerOfCondition, conditionForAnswer, noAnswer, inputBefore, yesAnswer } from '../choice-answers';
import type { Condition } from '../condition';
import type { InputState } from '../input-state';
import type { Process } from '../process';

const finish = { state_type: 'end', status: 'success' };
const rule = (next: string, when: unknown = { op: 'is_true', path: 'ok' }) => ({ when, next });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

// An input with only the keys the functions read.
const input = (schema: unknown, assign = 'answer') => ({ schema, assign }) as Pick<InputState, 'schema' | 'assign'>;

const yesOrNo = input({ kind: 'boolean' }, 'ok');
const chooseOne = input({ kind: 'select_one', options: [{ value: 'post', label: 'By post' }, { value: 'online', label: 'Online' }] }, 'method');

describe('inputBefore', () => {
	const ask = { state_type: 'input', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'decide' };
	const decide = { state_type: 'choice', rules: [rule('yes')], default: 'no' };

	it('finds the input whose next is the decision', () => {
		const found = inputBefore(build('ask', { ask, decide, yes: finish, no: finish }), 'decide');
		expect(found?.code).toBe('ask');
		expect(found?.input.assign).toBe('ok');
	});

	it('finds none when a message leads to the decision', () => {
		const say = { state_type: 'output', channel: 'transcript', message: 'Hello', next: 'decide' };
		expect(inputBefore(build('say', { say, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when two states lead to the decision, or none does', () => {
		const other = { ...ask, next: 'decide' };
		expect(inputBefore(build('ask', { ask, other, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
		expect(inputBefore(build('ask', { ask: { ...ask, next: 'yes' }, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when the input only leads to the decision by a route for an invalid answer', () => {
		const invalid = { ...ask, next: 'yes', on_invalid: 'decide' };
		expect(inputBefore(build('ask', { ask: invalid, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});

	it('finds none when the decision is the start of the process', () => {
		expect(inputBefore(build('decide', { ask, decide, yes: finish, no: finish }), 'decide')).toBeUndefined();
	});
});

describe('answerChoices', () => {
	it('offers yes and no for a yes or no input', () => {
		expect(answerChoices(yesOrNo)).toEqual([
			{ value: yesAnswer, label: 'Yes' },
			{ value: noAnswer, label: 'No' }
		]);
	});

	it('offers the options of an input where the person chooses one or several', () => {
		expect(answerChoices(chooseOne).map((choice) => choice.label)).toEqual(['By post', 'Online']);
		expect(answerChoices(input({ kind: 'select_many', options: [{ value: 'a', label: 'A' }] }))).toEqual([{ value: 'a', label: 'A' }]);
	});

	it('offers nothing for an input answered by typing, by a file, or with options read at run time', () => {
		expect(answerChoices(input({ kind: 'string' }))).toEqual([]);
		expect(answerChoices(input({ kind: 'file_ref' }))).toEqual([]);
		expect(answerChoices(input({ kind: 'select_one', options_from: 'list' }))).toEqual([]);
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

	it('writes nothing for an answer the input does not offer', () => {
		expect(conditionForAnswer(chooseOne, 'by_phone')).toBeUndefined();
		expect(conditionForAnswer(input({ kind: 'string' }), 'anything')).toBeUndefined();
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
	// Every rule of every decision in the converted forms, with the input the decision follows. The demo form is
	// left out, because its added decision follows an API call and tests what the call saved.
	const rules = formExamples.filter((example) => !example.slug.endsWith('_with_submit')).flatMap((example) =>
		Object.values(example.workflow?.processes ?? {}).flatMap((process) =>
			Object.entries(process.states).flatMap(([code, state]) =>
				state.state_type === 'choice' ? state.rules.map((each) => ({ slug: example.slug, code, when: each.when, before: inputBefore(process, code) })) : []
			)
		)
	);

	it('all follow a single input', () => {
		expect(rules).toHaveLength(44);
		for (const each of rules) expect(each.before, `${each.slug}: ${each.code}`).toBeDefined();
	});

	it('are each read as an answer of that input, and written back exactly', () => {
		for (const each of rules) {
			const answer = answerOfCondition(each.before!.input, each.when);
			expect(answer, `${each.slug}: ${each.code}`).toBeDefined();
			expect(conditionForAnswer(each.before!.input, answer!)).toEqual(each.when);
		}
	});
});
