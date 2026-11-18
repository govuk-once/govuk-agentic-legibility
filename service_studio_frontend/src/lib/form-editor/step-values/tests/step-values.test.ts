import { describe, expect, it } from 'vitest';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { developerSteps, stepValuesSummary, withEntryState } from '../step-values';

// A short journey with a question, an assign, a wait and an API call, met in that order.
const workflow = {
	manifest: { entry: 'demo' },
	processes: {
		demo: {
			process_id: 'demo',
			version: '0.1.0',
			start: 'ask',
			states: {
				ask: { state_type: 'input', prompt: 'What is your name?', schema: { kind: 'string' }, assign: 'name', next: 'save' },
				save: { state_type: 'assign', name: 'Save name', set: { 'answers.name': { $: 'name' } }, next: 'pause' },
				pause: { state_type: 'wait', name: 'Wait a moment', duration: 'PT30M', next: 'send' },
				send: { state_type: 'api_call', name: 'Send form', method: 'POST', service: 'govuk_forms', url: '/send', assign: 'reply', next: 'done' },
				done: { state_type: 'end', status: 'success' }
			}
		}
	}
} as unknown as Workflow;

const states = workflow.processes.demo.states;

describe('developerSteps', () => {
	it('lists only the developer steps, in journey order', () => {
		expect(developerSteps(workflow).map((step) => [step.code, step.title])).toEqual([
			['save', 'Save name'],
			['pause', 'Wait a moment'],
			['send', 'Send form']
		]);
	});
});

describe('stepValuesSummary', () => {
	it('writes the main values of each kind of developer step on one line', () => {
		expect(stepValuesSummary(states.send)).toBe('POST · govuk_forms · assign reply');
		expect(stepValuesSummary(states.save)).toBe('sets answers.name');
		expect(stepValuesSummary(states.pause)).toBe('PT30M');
	});
});

describe('withEntryState', () => {
	it('replaces one state of the main process and keeps the rest', () => {
		const changed = withEntryState(workflow, 'pause', { ...states.pause, duration: 'PT1H' } as typeof states.pause);
		expect(changed.processes.demo.states.pause).toMatchObject({ duration: 'PT1H', next: 'send' });
		expect(changed.processes.demo.states.send).toBe(states.send);
	});
});
