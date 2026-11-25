import { z } from 'zod';
import { comparisonCondition, dateComparisonOperators } from './condition';
import { dynamicRefSchema, variablePathSchema } from './primitives';

/*
	The Expression from section 2.8 of the unified class structure document. An expression is the
	value that an assign state stores, an end state returns, an invoke state passes in, or an output
	state fills a template with. The document lists four forms: a literal, a reference, integer
	addition and date arithmetic, plus a date comparison that gives a true or false answer.

	1. now_plus is not in the document, but the change of address example uses it to set a deadline
	   from the current time plus a duration held in a variable. It is accepted so the examples
	   validate.
	2. The document says a literal object has no special keys. An object with a $ key or an op key
	   is therefore never treated as a literal, so a mistyped reference or operation fails instead
	   of being saved as data.
	3. A literal object or list may hold further expressions, because the examples build objects such
	   as { "driver_id": { "$": "driver.driver_id" } } from several references.
	4. append is not in the document, but the form files use it to keep each answer of a question that is asked more
	   than once. The executor keeps its assign operations in a register, and the published schema accepts any
	   expression, so it is accepted. The list of operations is a question for the executor team.
*/

// Integer addition on a variable, used to count attempts, for example upload_attempts plus 1.
const arithmeticExpression = z.strictObject({
	op: z.literal('add'),
	path: variablePathSchema,
	value: z.number().int()
});

// Date arithmetic with an offset written in plain words such as "39 weeks". The document gives no
// stricter format, so any non empty text is accepted.
const dateOffsetExpression = z.strictObject({
	op: z.enum(['date_add', 'date_subtract']),
	path: variablePathSchema,
	value: z.string().min(1)
});

// The current time plus a duration that is held in a variable, used to work out a deadline.
const nowPlusExpression = z.strictObject({
	op: z.literal('now_plus'),
	value_path: variablePathSchema
});

// Adds the value held at value_path to the end of the list held at path, used to keep every answer of a repeated question.
const appendExpression = z.strictObject({
	op: z.literal('append'),
	path: variablePathSchema,
	value_path: variablePathSchema
});

// A date comparison gives a true or false value. It has the same shape as the date comparisons in
// a condition, so it reuses that schema and only narrows the operator to the two date operators.
const dateComparisonExpression = comparisonCondition.refine(
	(expression) => (dateComparisonOperators as readonly string[]).includes(expression.op),
	{ message: 'Only date_before and date_diff_greater_than can be used as an expression' }
);

const operationExpressionSchema = z.discriminatedUnion('op', [
	arithmeticExpression,
	dateOffsetExpression,
	nowPlusExpression,
	appendExpression,
	dateComparisonExpression
]);

// The recursive type is written out by hand because a schema cannot infer a type that refers to itself.
export type Expression =
	| string
	| number
	| boolean
	| null
	| z.infer<typeof dynamicRefSchema>
	| z.infer<typeof operationExpressionSchema>
	| Expression[]
	| { [key: string]: Expression };

// A literal object has no $ or op key, otherwise it would be a reference or an operation.
const literalObject = z
	.record(
		z.string(),
		z.lazy(() => expressionSchema)
	)
	.refine((object) => !('$' in object) && !('op' in object), {
		message: 'A literal object cannot use $ or op as a key'
	});

export const expressionSchema: z.ZodType<Expression> = z.union([
	dynamicRefSchema,
	operationExpressionSchema,
	z.string(),
	z.number(),
	z.boolean(),
	z.null(),
	z.array(z.lazy(() => expressionSchema)),
	literalObject
]);
