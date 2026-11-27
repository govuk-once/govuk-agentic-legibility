import { describe, expect, it } from 'vitest';
import { editableOptions, newOption, withOptions } from '$lib/schema/workflow/answer-options';
import type { WorkingState } from '$lib/schema/workflow/working-process';

const chooseOne: WorkingState = {
	state_type: 'input',
	prompt: 'Which?',
	schema: {
		kind: 'select_one',
		options: [
			{ value: 'option_1', label: 'Option 1' },
			{ value: 'option_2', label: 'Option 2' }
		]
	},
	assign: 'which'
};

describe('editableOptions', () => {
	it('gives the options written out in a choice input', () => {
		expect(editableOptions(chooseOne)).toHaveLength(2);
	});

	it('gives none for an input that reads its options from a variable, or is not a choice', () => {
		expect(editableOptions({ ...chooseOne, schema: { kind: 'select_one', options_from: 'list' } })).toBeUndefined();
		expect(editableOptions({ ...chooseOne, schema: { kind: 'string' } })).toBeUndefined();
		expect(editableOptions({ state_type: 'output', channel: 'transcript', message: 'Hello' })).toBeUndefined();
	});
});

describe('newOption', () => {
	it('numbers the new option after the ones already there', () => {
		expect(newOption([{ value: 'option_1', label: 'A' }])).toEqual({ value: 'option_2', label: 'Option 2' });
	});

	it('never reuses a value another option still has, after one before it was removed', () => {
		expect(newOption([{ value: 'option_2', label: 'B' }]).value).toBe('option_3');
	});
});

describe('withOptions', () => {
	it('gives the input the new options with their labels tidied and their values kept', () => {
		const changed = withOptions(chooseOne, [
			{ value: 'option_1', label: '  Employed ' },
			{ value: 'option_3', label: 'Unemployed' }
		]);
		expect(editableOptions(changed)).toEqual([
			{ value: 'option_1', label: 'Employed' },
			{ value: 'option_3', label: 'Unemployed' }
		]);
	});

	it('leaves a state with no options to change as it is', () => {
		const typed: WorkingState = { ...chooseOne, schema: { kind: 'string' } };
		expect(withOptions(typed, [{ value: 'x', label: 'X' }])).toBe(typed);
	});
});
