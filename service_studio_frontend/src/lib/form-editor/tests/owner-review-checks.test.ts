import { describe, expect, it } from 'vitest';
import type { StateRow } from '$lib/process-graph/state-rows';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { exampleProblems, journeySteps, problemCount } from '../owner-review-checks';

// Numbered steps with only the keys the example problems read.
const stepsOf = (count: number): StateRow[] =>
	Array.from({ length: count }, (_, index) => ({
		stateId: `step_${index + 1}`,
		title: `Step title ${index + 1}`,
		number: index + 1,
		stateType: 'input'
	}));

describe('journeySteps', () => {
	it('lists the questions and messages in journey order with their numbers, and leaves out decisions, ends and assigns', () => {
		const process = {
			process_id: 'form',
			version: '0.1.0',
			start: 'name',
			states: {
				name: { state_type: 'input', prompt: 'What is your name?', schema: { kind: 'string' }, assign: 'answers.name', next: 'save' },
				save: { state_type: 'assign', set: { 'answers.saved': true }, next: 'more' },
				more: {
					state_type: 'choice',
					rules: [{ when: { '==': [{ var: 'answers.name' }, 'Sam'] }, next: 'thanks' }],
					default: 'done'
				},
				thanks: { state_type: 'output', channel: 'transcript', message: 'Thank you', next: 'done' },
				done: { state_type: 'end', status: 'succeeded' }
			}
		} as unknown as WorkingProcess;

		expect(journeySteps(process).map((step) => [step.number, step.title, step.stateType])).toEqual([
			[1, 'Name', 'input'],
			[2, 'Thanks', 'output']
		]);
	});
});

describe('exampleProblems', () => {
	it('puts an error on the third step, a warning on the fourth and a pending check on the sixth', () => {
		expect(exampleProblems(stepsOf(10)).map((problem) => [problem.result, problem.stateId])).toEqual([
			['error', 'step_3'],
			['warning', 'step_4'],
			['pending', 'step_6']
		]);
	});

	it('names each step by its title and number', () => {
		expect(exampleProblems(stepsOf(10))[0].message).toBe(
			'Step title 3, step 3: the answer is not saved anywhere, so no later step can use it'
		);
	});

	it('gives a short form only the problems it has steps for', () => {
		expect(exampleProblems(stepsOf(4)).map((problem) => problem.result)).toEqual(['error', 'warning']);
		expect(exampleProblems(stepsOf(2))).toEqual([]);
	});
});

describe('problemCount', () => {
	it('counts each kind of problem in words', () => {
		expect(problemCount(exampleProblems(stepsOf(10)))).toBe('1 error, 1 warning, 1 pending');
	});

	it('leaves out a kind there are none of', () => {
		expect(problemCount(exampleProblems(stepsOf(4)))).toBe('1 error, 1 warning');
		expect(problemCount([])).toBe('');
	});

	it('uses the plural for more than one', () => {
		const twoErrors = [
			{ result: 'error' as const, stateId: 'a', message: '' },
			{ result: 'error' as const, stateId: 'b', message: '' }
		];
		expect(problemCount(twoErrors)).toBe('2 errors');
	});
});
