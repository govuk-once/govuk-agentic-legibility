import { describe, expect, it } from 'vitest';
import { expressionSchema } from '../expression';

type Example = { states?: Record<string, { type: string; [key: string]: unknown }> };

// Every process file in the two example services, loaded as parsed JSON.
const exampleFiles = import.meta.glob('../../../examples/services/*/*.json', {
	eager: true,
	import: 'default'
}) as Record<string, Example>;

// Reads the expression fields from every state in the example files. These are assign.set,
// end.return, invoke.input and output.params, the four places the document uses an expression.
function collectExpressions(): unknown[] {
	const fields: Record<string, string> = {
		assign: 'set',
		end: 'return',
		invoke: 'input',
		output: 'params'
	};
	const found: unknown[] = [];
	for (const file of Object.values(exampleFiles)) {
		for (const state of Object.values(file.states ?? {})) {
			const field = fields[state.type];
			if (field && field in state) found.push(state[field]);
		}
	}
	return found;
}

describe('expressionSchema with the real examples', () => {
	const expressions = collectExpressions();

	it('finds the expressions in the example files', () => {
		expect(expressions.length).toBeGreaterThan(30);
	});

	it('accepts every expression used in the example files', () => {
		for (const expression of expressions) {
			const result = expressionSchema.safeParse(expression);
			expect(result.success, JSON.stringify(expression)).toBe(true);
		}
	});
});

describe('expressionSchema literals', () => {
	it.each([['text'], [42], [true], [false], [null], [0], ['']])('accepts the literal %s', (literal) => {
		expect(expressionSchema.safeParse(literal).success).toBe(true);
	});

	it('accepts a list and an object of literals', () => {
		expect(expressionSchema.safeParse(['a', 1, null]).success).toBe(true);
		expect(expressionSchema.safeParse({ colour: 'red', size: 3 }).success).toBe(true);
	});

	it('accepts a literal object that holds references and operations', () => {
		const expression = {
			driver_id: { $: 'driver.driver_id' },
			attempts: { op: 'add', path: 'attempts', value: 1 }
		};
		expect(expressionSchema.safeParse(expression).success).toBe(true);
	});

	it('accepts a list that holds references', () => {
		expect(expressionSchema.safeParse([{ $: 'a' }, { $: 'b' }]).success).toBe(true);
	});

	it('rejects a value that is not JSON', () => {
		expect(expressionSchema.safeParse(undefined).success).toBe(false);
		expect(expressionSchema.safeParse(() => 'x').success).toBe(false);
	});
});

describe('expressionSchema references', () => {
	it('accepts a reference', () => {
		expect(expressionSchema.safeParse({ $: 'photocard_res.photo_id' }).success).toBe(true);
	});

	it('rejects a reference with an invalid path instead of treating it as data', () => {
		expect(expressionSchema.safeParse({ $: 'photo id' }).success).toBe(false);
	});

	it('rejects a reference with extra keys', () => {
		expect(expressionSchema.safeParse({ $: 'a', extra: 1 }).success).toBe(false);
	});
});

describe('expressionSchema operations', () => {
	it('accepts integer addition', () => {
		expect(expressionSchema.safeParse({ op: 'add', path: 'upload_attempts', value: 1 }).success).toBe(true);
	});

	it('rejects addition of a decimal or of text', () => {
		expect(expressionSchema.safeParse({ op: 'add', path: 'a', value: 1.5 }).success).toBe(false);
		expect(expressionSchema.safeParse({ op: 'add', path: 'a', value: '1' }).success).toBe(false);
	});

	it.each(['date_add', 'date_subtract'])('accepts %s with a text offset', (op) => {
		expect(expressionSchema.safeParse({ op, path: 'input.due_date', value: '39 weeks' }).success).toBe(true);
	});

	it('rejects date arithmetic with a missing or numeric offset', () => {
		expect(expressionSchema.safeParse({ op: 'date_add', path: 'a' }).success).toBe(false);
		expect(expressionSchema.safeParse({ op: 'date_add', path: 'a', value: 39 }).success).toBe(false);
	});

	it('accepts now_plus with a value_path', () => {
		expect(expressionSchema.safeParse({ op: 'now_plus', value_path: 'poll_window' }).success).toBe(true);
	});

	it('accepts the two date comparisons', () => {
		const before = { op: 'date_before', path: '__now__', value_path: 'actual_birth_date' };
		const difference = { op: 'date_diff_greater_than', path: 'input.actual_birth_date', value: '3 months' };
		expect(expressionSchema.safeParse(before).success).toBe(true);
		expect(expressionSchema.safeParse(difference).success).toBe(true);
	});

	it('rejects a comparison that is not a date comparison', () => {
		expect(expressionSchema.safeParse({ op: 'eq', path: 'a', value: 1 }).success).toBe(false);
	});

	it('rejects an unknown operator instead of treating it as data', () => {
		expect(expressionSchema.safeParse({ op: 'multiply', path: 'a', value: 2 }).success).toBe(false);
	});
});
