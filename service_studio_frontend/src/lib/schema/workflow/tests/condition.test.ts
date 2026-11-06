import { describe, expect, it } from 'vitest';
import { conditionSchema } from '../condition';

// Every workflow file in the two example services, loaded as parsed JSON.
const exampleFiles = import.meta.glob('../../../examples/services/*/*.json', {
	eager: true,
	import: 'default'
}) as Record<string, unknown>;

// Walks any JSON value and collects whatever sits under a key called "when", which is where a
// choice rule keeps its condition. Used to check every real rule in the examples.
function collectConditions(node: unknown, found: unknown[] = []): unknown[] {
	if (Array.isArray(node)) {
		node.forEach((item) => collectConditions(item, found));
	} else if (node && typeof node === 'object') {
		for (const [key, value] of Object.entries(node)) {
			if (key === 'when') found.push(value);
			else collectConditions(value, found);
		}
	}
	return found;
}

describe('conditionSchema with the real examples', () => {
	const conditions = collectConditions(Object.values(exampleFiles));

	it('finds the rules in the example files', () => {
		expect(conditions.length).toBeGreaterThan(50);
	});

	it('accepts every condition used in the example files', () => {
		for (const condition of conditions) {
			const result = conditionSchema.safeParse(condition);
			expect(result.success, JSON.stringify(condition)).toBe(true);
		}
	});
});

describe('conditionSchema comparisons', () => {
	it('accepts a path with a literal value', () => {
		expect(conditionSchema.safeParse({ op: 'gte', path: 'upload_attempts', value: 3 }).success).toBe(true);
		expect(conditionSchema.safeParse({ op: 'eq', path: 'job.state', value: 'COMPLETED' }).success).toBe(true);
	});

	it('accepts a path with a value_path', () => {
		const condition = { op: 'date_before', path: '__now__', value_path: 'actual_birth_date' };
		expect(conditionSchema.safeParse(condition).success).toBe(true);
	});

	it('accepts a value of false or zero', () => {
		expect(conditionSchema.safeParse({ op: 'eq', path: 'consent', value: false }).success).toBe(true);
		expect(conditionSchema.safeParse({ op: 'eq', path: 'attempts', value: 0 }).success).toBe(true);
	});

	it('rejects a comparison with no operand', () => {
		expect(conditionSchema.safeParse({ op: 'eq', path: 'job.state' }).success).toBe(false);
	});

	it('rejects a comparison with both value and value_path', () => {
		const condition = { op: 'eq', path: 'a', value: 1, value_path: 'b' };
		expect(conditionSchema.safeParse(condition).success).toBe(false);
	});

	it('rejects a comparison with no path', () => {
		expect(conditionSchema.safeParse({ op: 'eq', value: 1 }).success).toBe(false);
	});

	it('rejects an invalid path', () => {
		expect(conditionSchema.safeParse({ op: 'eq', path: 'a b', value: 1 }).success).toBe(false);
	});
});

describe('conditionSchema single value tests', () => {
	it.each(['is_true', 'is_false', 'not_empty', 'before_now'])('accepts %s with a path', (op) => {
		expect(conditionSchema.safeParse({ op, path: 'deadline' }).success).toBe(true);
	});

	it('rejects a single value test that carries an operand', () => {
		expect(conditionSchema.safeParse({ op: 'is_true', path: 'a', value: true }).success).toBe(false);
	});

	it('rejects a single value test with no path', () => {
		expect(conditionSchema.safeParse({ op: 'is_true' }).success).toBe(false);
	});
});

describe('conditionSchema logical operators', () => {
	const isTrue = { op: 'is_true', path: 'confirmed' };
	const attemptsReached = { op: 'gte', path: 'upload_attempts', value: 3 };

	it('accepts and, or with several conditions', () => {
		expect(conditionSchema.safeParse({ op: 'and', all: [isTrue, attemptsReached] }).success).toBe(true);
		expect(conditionSchema.safeParse({ op: 'or', all: [isTrue, attemptsReached] }).success).toBe(true);
	});

	it('accepts not with one condition', () => {
		expect(conditionSchema.safeParse({ op: 'not', all: [isTrue] }).success).toBe(true);
	});

	it('accepts conditions nested several levels deep', () => {
		const nested = { op: 'or', all: [isTrue, { op: 'and', all: [attemptsReached, { op: 'not', all: [isTrue] }] }] };
		expect(conditionSchema.safeParse(nested).success).toBe(true);
	});

	it('rejects an empty list for and, or', () => {
		expect(conditionSchema.safeParse({ op: 'and', all: [] }).success).toBe(false);
	});

	it('rejects not with more than one condition', () => {
		expect(conditionSchema.safeParse({ op: 'not', all: [isTrue, attemptsReached] }).success).toBe(false);
	});

	it('rejects a logical operator with no all list', () => {
		expect(conditionSchema.safeParse({ op: 'and' }).success).toBe(false);
	});

	it('rejects a malformed condition inside a nested list', () => {
		const condition = { op: 'and', all: [isTrue, { op: 'eq', path: 'a' }] };
		expect(conditionSchema.safeParse(condition).success).toBe(false);
	});

	it('rejects a path on a logical operator', () => {
		expect(conditionSchema.safeParse({ op: 'and', path: 'a', all: [isTrue] }).success).toBe(false);
	});
});

describe('conditionSchema operators', () => {
	it('rejects an operator the document does not list', () => {
		expect(conditionSchema.safeParse({ op: 'neq', path: 'a', value: 1 }).success).toBe(false);
	});

	it('rejects a value that is not a condition', () => {
		expect(conditionSchema.safeParse('is_true').success).toBe(false);
		expect(conditionSchema.safeParse(null).success).toBe(false);
	});
});
