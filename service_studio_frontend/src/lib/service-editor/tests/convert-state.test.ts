import { describe, expect, it } from 'vitest';
import { exampleStatesOfType } from '$lib/schema/workflow/tests/example-states';
import { convertState, convertTargetTypes, isConvertTargetType, isConvertible, lostByConversion } from '../schema/convert-state';
import { isUnconnectedApiCall, placeholderMessage, placeholderQuestion, placeholderWaitDuration } from '$lib/schema/workflow/placeholders';
import { stateSchema, type State } from '$lib/schema/workflow/process';

const state = (value: unknown) => value as State;
const sourceTypes = ['input', 'output', 'api_call', 'assign', 'invoke', 'wait'] as const;

const input = state({
	type: 'input',
	name: 'Ask',
	metadata: { description: 'Asks it.' },
	prompt: 'Is it right?',
	schema: { kind: 'boolean' },
	assign: 'ok',
	next: 'done',
	on_invalid: 'again',
	timeout: { after: 'PT5S', next: 'give_up' }
});

describe('convertState', () => {
	it('keeps the title, the notes and the next state, and carries the question across as the message', () => {
		const converted = convertState(input, 'output', 'ask');
		expect(converted).toEqual({
			type: 'output',
			name: 'Ask',
			metadata: { description: 'Asks it.' },
			channel: 'transcript',
			message: 'Is it right?',
			next: 'done'
		});
	});

	it('carries the message of a transcript output across as the question of an input', () => {
		const converted = convertState(state({ type: 'output', channel: 'transcript', message: 'Hello', next: 'done' }), 'input', 'say hello');
		expect(converted).toMatchObject({ type: 'input', prompt: 'Hello', schema: { kind: 'string' }, assign: 'answer_say_hello', next: 'done' });
	});

	it('uses a placeholder question or message when the old step had no words', () => {
		const wait = state({ type: 'wait', duration: 'PT1S', next: 'done' });
		expect(convertState(wait, 'input', 'a')).toMatchObject({ prompt: placeholderQuestion });
		expect(convertState(wait, 'output', 'a')).toMatchObject({ message: placeholderMessage });
		expect(convertState(state({ type: 'output', channel: 'email', template: 'receipt', next: 'done' }), 'input', 'a')).toMatchObject({
			prompt: placeholderQuestion
		});
	});

	it('makes a call that is not connected to a service yet, and a wait with a placeholder duration', () => {
		const call = convertState(input, 'api_call', 'ask');
		expect(call).toMatchObject({ type: 'api_call', next: 'done', assign: 'ok' });
		expect(isUnconnectedApiCall(call as Extract<State, { type: 'api_call' }>)).toBe(true);
		expect(convertState(input, 'wait', 'ask')).toMatchObject({ type: 'wait', duration: placeholderWaitDuration, next: 'done' });
	});

	it('keeps a key that both types have, such as where a result is saved and the error routes', () => {
		const call = state({ type: 'api_call', method: 'GET', service: 's', url: '/u', assign: 'res', catch: [{ on: 'any', next: 'sorry' }], next: 'done' });
		const invoke = state({ type: 'invoke', process: 'p', assign: 'res', catch: [{ on: 'any', next: 'sorry' }], next: 'done' });

		expect(convertState(call, 'input', 'a')).toMatchObject({ assign: 'res' });
		expect(convertState(invoke, 'api_call', 'a')).toMatchObject({ assign: 'res', catch: [{ on: 'any', next: 'sorry' }] });
	});

	it('returns a decision, an end or a step that is already that type as it is', () => {
		const choice = state({ type: 'choice', rules: [{ when: { op: 'is_true', path: 'a' }, next: 'x' }], default: 'y' });
		const end = state({ type: 'end', status: 'success' });
		expect(convertState(choice, 'output', 'a')).toBe(choice);
		expect(convertState(end, 'output', 'a')).toBe(end);
		expect(convertState(input, 'input', 'a')).toBe(input);
	});

	it('does not change the state it is given', () => {
		const before = JSON.stringify(input);
		convertState(input, 'api_call', 'ask');
		expect(JSON.stringify(input)).toBe(before);
	});

	it.each(sourceTypes)('gives every other type from a real %s state that the schema accepts', (source) => {
		const states = exampleStatesOfType(source);
		expect(states.length).toBeGreaterThan(0);

		for (const real of states) {
			for (const target of convertTargetTypes) {
				const converted = convertState(state(real), target, 'some state-code');
				expect(stateSchema.safeParse(converted).success, `${source} to ${target}`).toBe(true);
				expect(converted.type).toBe(target);
			}
		}
	});
});

describe('lostByConversion', () => {
	it('lists in plain words what an input loses when it becomes an output', () => {
		expect(lostByConversion(input, 'output')).toEqual([
			'the answer type',
			'where the answer is saved',
			'the route for an invalid answer',
			'the timeout'
		]);
	});

	it('does not count the question as lost, because it is carried across as the message', () => {
		expect(lostByConversion(input, 'output')).not.toContain('the question');
	});

	it('counts the words as lost when the other type has none', () => {
		expect(lostByConversion(input, 'wait')).toContain('the question');
		expect(lostByConversion(state({ type: 'output', channel: 'email', template: 'receipt', next: 'done' }), 'input')).toEqual([
			'the channel',
			'the template'
		]);
	});

	it('names the three keys of a request once', () => {
		const call = state({ type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'done' });
		expect(lostByConversion(call, 'wait')).toEqual(['the request']);
	});

	it('lists nothing when the type does not change or nothing is lost', () => {
		expect(lostByConversion(input, 'input')).toEqual([]);
		expect(lostByConversion(state({ type: 'wait', duration: 'PT1S', next: 'done' }), 'assign')).toEqual(['how long it waits']);
		expect(lostByConversion(state({ type: 'assign', set: {}, next: 'done' }), 'wait')).toEqual(['the values it sets']);
	});

	it('lists nothing for a decision or an end', () => {
		expect(lostByConversion(state({ type: 'end', status: 'success' }), 'output')).toEqual([]);
	});
});

describe('isConvertible', () => {
	it('is true for every type with one next state and false for a decision or an end', () => {
		for (const type of sourceTypes) expect(isConvertible(state({ type }))).toBe(true);
		expect(isConvertible(state({ type: 'choice' }))).toBe(false);
		expect(isConvertible(state({ type: 'end' }))).toBe(false);
	});
});

describe('isConvertTargetType', () => {
	it('is true for the types a step can become and false for invoke, a decision, an end and other text', () => {
		for (const type of convertTargetTypes) expect(isConvertTargetType(type)).toBe(true);
		for (const type of ['invoke', 'choice', 'end', 'banana']) expect(isConvertTargetType(type)).toBe(false);
	});
});
