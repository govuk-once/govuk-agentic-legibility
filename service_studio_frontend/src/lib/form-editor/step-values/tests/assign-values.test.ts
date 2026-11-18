import { describe, expect, it } from 'vitest';
import type { AssignState } from '$lib/schema/workflow/states';
import { assignKindOf, assignLinesOf, assignPartField, assignVariableField, assignWithLines } from '../assign-values';

const assign: AssignState = {
	state_type: 'assign',
	name: 'Append answer',
	set: {
		'answers.step_3': { op: 'append', path: 'answers.step_3', value_path: 'repeat.step_3.current' },
		attempts: { op: 'add', path: 'attempts', value: 1 }
	},
	next: 'more'
};

describe('assignKindOf', () => {
	it('tells a fixed value, a copy and each operation apart', () => {
		expect(assignKindOf('yes')).toBe('literal');
		expect(assignKindOf({ a: 1 })).toBe('literal');
		expect(assignKindOf({ $: 'name' })).toBe('copy');
		expect(assignKindOf({ op: 'date_subtract', path: 'due', value: '2 weeks' })).toBe('date_offset');
		expect(assignKindOf({ op: 'now_plus', value_path: 'wait' })).toBe('now_plus');
	});
});

describe('assignLinesOf', () => {
	it('lists each variable with its kind and the parts of its value, without the op', () => {
		expect(assignLinesOf(assign)).toEqual([
			{
				variable: 'answers.step_3',
				kind: 'append',
				parts: [
					{ name: 'path', label: 'Path', text: 'answers.step_3' },
					{ name: 'value_path', label: 'Value from', text: 'repeat.step_3.current' }
				]
			},
			{
				variable: 'attempts',
				kind: 'add',
				parts: [
					{ name: 'path', label: 'Path', text: 'attempts' },
					{ name: 'value', label: 'Value', text: '1' }
				]
			}
		]);
	});
});

describe('assignWithLines', () => {
	it('reads the typed parts back, keeping each kind and a number as a number', () => {
		const result = assignWithLines(assign, [
			{ variable: 'answers.trainers', parts: ['answers.trainers', 'repeat.current'] },
			{ variable: 'attempts', parts: ['attempts', '2'] }
		]);
		expect(result).toEqual({
			ok: true,
			state: {
				...assign,
				set: {
					'answers.trainers': { op: 'append', path: 'answers.trainers', value_path: 'repeat.current' },
					attempts: { op: 'add', path: 'attempts', value: 2 }
				}
			}
		});
	});

	it('names the variable and the part that must be put right', () => {
		const result = assignWithLines(assign, [
			{ variable: 'not a name', parts: ['answers.step_3', 'repeat.step_3.current'] },
			{ variable: 'attempts', parts: ['attempts', 'two'] }
		]);
		expect(result.ok ? [] : result.problems.map((problem) => problem.field)).toEqual([assignVariableField(0), assignPartField(1, 1)]);
	});

	it('refuses a variable that is set twice', () => {
		const result = assignWithLines(assign, [
			{ variable: 'attempts', parts: ['answers.step_3', 'repeat.step_3.current'] },
			{ variable: 'attempts', parts: ['attempts', '1'] }
		]);
		expect(result.ok ? [] : result.problems).toEqual([{ field: assignVariableField(1), message: 'attempts is set more than once' }]);
	});
});
