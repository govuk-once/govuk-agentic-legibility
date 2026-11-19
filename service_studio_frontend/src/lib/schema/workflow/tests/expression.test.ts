import { describe, expect, it } from 'vitest';
import { expressionSchema } from '../expression';
import { assignStateSchema } from '../states';

type Example = { states?: Record<string, { state_type: string; [key: string]: unknown }> };

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
			const field = fields[state.state_type];
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

	describe('append, as the form files write it', () => {
		const append = { op: 'append', path: 'answers.step_3', value_path: 'repeat.step_3.current' };

		it('accepts adding the value at value_path to the list at path', () => {
			expect(expressionSchema.safeParse(append).success).toBe(true);
		});

		it.each(['path', 'value_path'])('refuses an append with no %s', (key) => {
			const { [key]: _removed, ...incomplete } = append as Record<string, string>;
			expect(expressionSchema.safeParse(incomplete).success).toBe(false);
		});

		it('refuses an append with a key it does not use, or a path that is not a variable path', () => {
			expect(expressionSchema.safeParse({ ...append, value: 1 }).success).toBe(false);
			expect(expressionSchema.safeParse({ ...append, path: 'not a path' }).success).toBe(false);
		});

		it('is accepted in the set of an assign state, as the form files use it', () => {
			const state = { state_type: 'assign', name: 'Append Answer', metadata: {}, set: { 'answers.step_3': append }, next: 'step_3_more' };
			expect(assignStateSchema.safeParse(state).success).toBe(true);
		});
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
