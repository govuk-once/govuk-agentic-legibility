import { describe, expect, it } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import type { Condition } from '$lib/schema/workflow/condition';
import type { Expression } from '$lib/schema/workflow/expression';
import { describeCondition, describeDuration, describeExpression } from '../describe-value';

describe('describeDuration', () => {
	it.each([
		['PT5S', '5 seconds'],
		['PT1S', '1 second'],
		['PT30M', '30 minutes'],
		['P14D', '14 days'],
		['P1W', '1 week'],
		['P1DT12H', '1 day and 12 hours'],
		['P1Y2M', '1 year and 2 months']
	])('writes %s as %s', (duration, words) => {
		expect(describeDuration(duration)).toBe(words);
	});

	it('names the variable when the duration is held in one', () => {
		expect(describeDuration({ $: 'settings.reminder' })).toBe('the time held in settings.reminder');
	});

	it('returns text that is not a duration as it is', () => {
		expect(describeDuration('soon')).toBe('soon');
	});
});

describe('describeCondition', () => {
	const sentence = (condition: unknown) => describeCondition(condition as Condition);

	it('writes a test on one variable', () => {
		expect(sentence({ op: 'is_true', path: 'photo.expired' })).toBe('photo.expired is true');
		expect(sentence({ op: 'is_false', path: 'photo.expired' })).toBe('photo.expired is false');
		expect(sentence({ op: 'not_empty', path: 'upload.ref' })).toBe('upload.ref has a value');
		expect(sentence({ op: 'before_now', path: 'deadline' })).toBe('deadline is before now');
	});

	it('writes a comparison with a value, quoting text and not numbers', () => {
		expect(sentence({ op: 'eq', path: 'job.state', value: 'COMPLETED' })).toBe('job.state is "COMPLETED"');
		expect(sentence({ op: 'gte', path: 'upload_attempts', value: 3 })).toBe('upload_attempts is at least 3');
		expect(sentence({ op: 'contains', path: 'jobs', value: 'outside_uk' })).toBe('jobs contains "outside_uk"');
	});

	it('writes a date difference as greater than the amount', () => {
		expect(sentence({ op: 'date_diff_greater_than', path: 'input.birth_date', value: '3 months' })).toBe(
			'input.birth_date is greater than "3 months"'
		);
	});

	it('writes a comparison with another variable and calls the special path now', () => {
		expect(sentence({ op: 'date_before', path: '__now__', value_path: 'birth_date' })).toBe('now is before birth_date');
	});

	it('joins and or or, and puts a group inside a group in brackets', () => {
		const inner = { op: 'or', all: [{ op: 'is_true', path: 'b' }, { op: 'is_true', path: 'c' }] };
		expect(sentence({ op: 'and', all: [{ op: 'is_true', path: 'a' }, inner] })).toBe('a is true and (b is true or c is true)');
	});

	it('writes not around the condition it negates', () => {
		expect(sentence({ op: 'not', all: [{ op: 'is_true', path: 'a' }] })).toBe('not (a is true)');
	});

	it('describes every condition in both real examples', () => {
		const conditions: Condition[] = [];
		for (const example of serviceExamples) {
			for (const process of Object.values(example.workflow?.processes ?? {})) {
				for (const state of Object.values(process.states)) {
					if (state.state_type === 'choice') conditions.push(...state.rules.map((rule) => rule.when));
				}
			}
		}

		expect(conditions.length).toBeGreaterThan(0);
		for (const condition of conditions) expect(describeCondition(condition).length).toBeGreaterThan(0);
	});
});

describe('describeExpression', () => {
	const sentence = (expression: unknown) => describeExpression(expression as Expression);

	it('writes values as they are written in the file', () => {
		expect(sentence('text')).toBe('"text"');
		expect(sentence(3)).toBe('3');
		expect(sentence(true)).toBe('true');
		expect(sentence(null)).toBe('null');
		expect(sentence(['a', 1])).toBe('["a", 1]');
	});

	it('writes a reference as the variable name', () => {
		expect(sentence({ $: 'driver.id' })).toBe('driver.id');
	});

	it('writes sums, date offsets and the time now plus a duration', () => {
		expect(sentence({ op: 'add', path: 'attempts', value: 1 })).toBe('attempts plus 1');
		expect(sentence({ op: 'date_add', path: 'start', value: '39 weeks' })).toBe('start plus 39 weeks');
		expect(sentence({ op: 'date_subtract', path: 'due', value: '66 weeks' })).toBe('due minus 66 weeks');
		expect(sentence({ op: 'now_plus', value_path: 'settings.wait' })).toBe('now plus settings.wait');
	});

	it('writes a date comparison like a condition', () => {
		expect(sentence({ op: 'date_before', path: '__now__', value_path: 'birth' })).toBe('now is before birth');
	});

	it('writes an object with each of its values described', () => {
		expect(sentence({ driver_id: { $: 'driver.id' }, retries: 2 })).toBe('{ driver_id: driver.id, retries: 2 }');
	});
});
