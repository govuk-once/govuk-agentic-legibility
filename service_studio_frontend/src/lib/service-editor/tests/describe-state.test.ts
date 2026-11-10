import { describe, expect, it } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import type { State } from '$lib/schema/workflow/process';
import { describeState } from '../graph/describe-state';
import { stateTitle } from '$lib/process-graph/process-to-graph';

const state = (value: unknown) => value as State;
const titles: Record<string, string> = { done: 'All done', retry: 'Try again', sorry: 'Say sorry' };
const titleOf = (code: string) => titles[code];

describe('describeState facts', () => {
	it('describes an input by its question, answer type and the variable it is saved in', () => {
		const described = describeState(
			state({ type: 'input', prompt: 'Which one?', schema: { kind: 'select_one', options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }] }, assign: 'choice', next: 'done' }),
			'ask',
			titleOf
		);
		expect(described.facts).toEqual([
			{ label: 'Question', value: 'Which one?', main: true },
			{ label: 'Answer type', value: 'select_one' },
			{ label: 'Choices', value: 'A, B' },
			{ label: 'Saved as', value: 'choice' }
		]);
	});

	it('describes an output by its channel and message', () => {
		const described = describeState(state({ type: 'output', channel: 'transcript', message: 'Hello', next: 'done' }), 'say', titleOf);
		expect(described.facts).toEqual([
			{ label: 'Channel', value: 'transcript' },
			{ label: 'Message', value: 'Hello', main: true }
		]);
	});

	it('describes a call by its request and what it keeps', () => {
		const described = describeState(
			state({ type: 'api_call', method: 'GET', service: 'dvla', url: '/licence', assign: 'res', capture: { name: 'body.name' }, next: 'done' }),
			'fetch',
			titleOf
		);
		expect(described.facts).toEqual([
			{ label: 'Request', value: 'GET dvla/licence', main: true },
			{ label: 'Response saved as', value: 'res' },
			{ label: 'Keeps', value: 'name' }
		]);
	});

	it('describes an assign by each variable it sets', () => {
		const described = describeState(state({ type: 'assign', set: { attempts: { op: 'add', path: 'attempts', value: 1 } }, next: 'done' }), 'count', titleOf);
		expect(described.facts).toEqual([{ label: 'Sets attempts', value: 'attempts plus 1', main: true }]);
	});

	it('describes an invoke by the process it runs and offers to open it', () => {
		const described = describeState(
			state({ type: 'invoke', process: 'photo_update', input: { id: { $: 'driver.id' } }, assign: 'photo', next: 'done' }),
			'run',
			titleOf
		);
		expect(described.facts).toEqual([
			{ label: 'Runs process', value: 'Photo update' },
			{ label: 'Passes in id', value: 'driver.id' },
			{ label: 'Result saved as', value: 'photo' }
		]);
		expect(described.opensProcess).toEqual({ id: 'photo_update', title: 'Photo update' });
	});

	it('describes a wait by how long it waits', () => {
		const described = describeState(state({ type: 'wait', duration: 'PT2S', next: 'done' }), 'pause', titleOf);
		expect(described.facts).toEqual([{ label: 'Waits for', value: '2 seconds', main: true }]);
	});

	it('describes an end by its status and outcome', () => {
		const described = describeState(state({ type: 'end', status: 'cancelled', outcome: 'user_cancelled' }), 'stop', titleOf);
		expect(described.facts).toEqual([
			{ label: 'Finishes as', value: 'cancelled', main: true },
			{ label: 'Outcome', value: 'user_cancelled' }
		]);
		expect(described.routes).toEqual([]);
	});

	it('gives a choice no facts, because its rules are its routes', () => {
		const described = describeState(state({ type: 'choice', rules: [{ when: { op: 'is_true', path: 'a' }, next: 'done' }], default: 'retry' }), 'check', titleOf);
		expect(described.facts).toEqual([]);
	});
});

describe('describeState routes', () => {
	it('says when each route of a choice is taken, in the order they are tested', () => {
		const described = describeState(
			state({ type: 'choice', rules: [{ when: { op: 'is_true', path: 'a' }, next: 'done' }], default: 'retry' }),
			'check',
			titleOf
		);
		expect(described.routes).toEqual([
			{ label: 'If a is true', kind: 'rule', targetId: 'done', targetTitle: 'All done' },
			{ label: 'Otherwise', kind: 'default', targetId: 'retry', targetTitle: 'Try again' }
		]);
	});

	it('says when the invalid answer and timeout routes of an input are taken', () => {
		const described = describeState(
			state({ type: 'input', prompt: 'Q', schema: { kind: 'boolean' }, assign: 'a', next: 'done', on_invalid: 'retry', timeout: { after: 'PT30S', next: 'sorry' } }),
			'ask',
			titleOf
		);
		expect(described.routes.map((route) => route.label)).toEqual([
			'Next',
			'If the answer is not valid',
			'If there is no answer after 30 seconds'
		]);
	});

	it('names the error in a catch route, and treats any as anything going wrong', () => {
		const call = describeState(
			state({ type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'done', catch: [{ on: 'api_failure', next: 'sorry' }, { on: 'any', next: 'retry' }] }),
			'fetch',
			titleOf
		);
		expect(call.routes.map((route) => route.label)).toEqual(['Next', 'If the call fails with api_failure', 'If anything goes wrong']);

		const invoke = describeState(state({ type: 'invoke', process: 'p', next: 'done', catch: [{ on: 'cancelled', next: 'sorry' }] }), 'run', titleOf);
		expect(invoke.routes[1].label).toBe('If the process ends with cancelled');
	});

	it('names a target that does not exist as missing', () => {
		const described = describeState(state({ type: 'wait', duration: 'PT1S', next: 'nowhere' }), 'pause', titleOf);
		expect(described.routes[0]).toEqual({ label: 'Next', kind: 'next', targetId: 'nowhere', targetTitle: 'nowhere (missing)' });
	});
});

describe('describeState with the real examples', () => {
	it('describes every state of every real process with a label on each route', () => {
		let described = 0;
		for (const example of serviceExamples) {
			for (const process of Object.values(example.workflow?.processes ?? {})) {
				const titleOfState = (code: string) => (process.states[code] ? stateTitle(process.states[code], code) : undefined);
				for (const [code, real] of Object.entries(process.states)) {
					const result = describeState(real, code, titleOfState);
					described += 1;
					expect(result.stateType).toBe(real.type);
					for (const route of result.routes) {
						expect(route.label.length, `${process.process_id}.${code}`).toBeGreaterThan(0);
						expect(route.targetTitle, `${process.process_id}.${code}`).not.toContain('(missing)');
					}
				}
			}
		}
		expect(described).toBe(260);
	});
});
