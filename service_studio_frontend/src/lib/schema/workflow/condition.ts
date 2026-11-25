import { z } from 'zod';
import { variablePathSchema } from './primitives';

/*
	The Condition from section 2.5 of the unified class structure document. A choice state uses one
	for each rule, and an input timeout or a wait never does. The document describes a single object
	with op, path, value, value_path and all. It is split here by operator family so that each family
	only accepts the keys it can use, for example is_true takes a path and nothing else.

	1. The document does not say which keys each operator needs. The split below follows how the two
	   example workflows use them: comparisons take a path and one operand, single value tests take a
	   path only, and and, or, not take a list called all.
	2. A comparison takes either value or value_path, never both, because the document calls
	   value_path the alternative to value.
	3. not reuses the all list, as the document names no other field for it. It must hold exactly
	   one condition.
*/

// The date operators have their own list because section 2.8 also allows them as an expression, so
// the expression schema can reuse the same shape instead of repeating it.
export const dateComparisonOperators = ['date_before', 'date_diff_greater_than'] as const;

// The operators that compare the value at a path with one operand. The date operators are included
// because the document gives them the same path and operand shape.
const comparisonOperators = ['eq', 'lt', 'lte', 'gt', 'gte', 'contains', ...dateComparisonOperators] as const;

// The operators that test the value at a path on its own, so they need no operand.
const singleValueOperators = ['is_true', 'is_false', 'not_empty', 'before_now'] as const;

// A comparison operand is a literal JSON value, kept as JSON so that a function or a date object
// cannot be saved by mistake.
export const comparisonCondition = z
	.strictObject({
		op: z.enum(comparisonOperators),
		path: variablePathSchema,
		value: z.json().optional(),
		value_path: variablePathSchema.optional()
	})
	.refine((condition) => (condition.value !== undefined) !== (condition.value_path !== undefined), {
		message: 'Give either value or value_path, but not both and not neither'
	});

const singleValueCondition = z.strictObject({
	op: z.enum(singleValueOperators),
	path: variablePathSchema
});

// and and or join a list of sub conditions. The list refers back to the full condition schema, so
// the getter delays that lookup until the schema has finished being built.
const andOrCondition = z.strictObject({
	op: z.enum(['and', 'or']),
	get all(): z.ZodArray<typeof conditionSchema> {
		return z.array(conditionSchema).min(1, 'Give at least one condition');
	}
});

// not negates one sub condition, held as a list of one so that it shares the all field with and, or.
const notCondition = z.strictObject({
	op: z.literal('not'),
	get all(): z.ZodArray<typeof conditionSchema> {
		return z.array(conditionSchema).length(1, 'not takes exactly one condition');
	}
});

export const conditionSchema = z.discriminatedUnion('op', [
	comparisonCondition,
	singleValueCondition,
	andOrCondition,
	notCondition
]);

export type Condition = z.infer<typeof conditionSchema>;
