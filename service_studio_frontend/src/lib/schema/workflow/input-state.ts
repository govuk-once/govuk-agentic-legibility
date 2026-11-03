import { z } from 'zod';
import { stateCommonFields } from './states';
import { durationOrRefSchema, stateRefSchema, variablePathSchema } from './primitives';

/*
	The input state from section 1.7 of the unified class structure document, with its answer
	definition (SchemaDefinition, section 2.1), option item (2.2) and timeout (2.3).

	1. The document says the kind decides which keys of the answer definition apply. It is split by
	   kind here, so a pattern can only sit on a string answer and options only on a choice answer.
	2. The fields key is not modelled. The document never defines FieldDefinition and no example uses
	   it, because each input state asks one question.
	3. normalise accepts lower_trim as well as upper_trim. The document lists only upper_trim, but
	   the change of address example uses lower_trim for email addresses.
	4. The document does not say which keys are required. A select answer needs options or
	   options_from, because without one there is nothing to choose between.
*/

// Keys that make sense for every kind of answer. allow_skip lets the person leave the question blank.
const commonAnswerFields = {
	invalid_message: z.string().min(1).optional(),
	allow_skip: z.boolean().optional()
};

// One choice offered to the person. The value is stored and the label is shown.
const optionItemSchema = z.strictObject({ value: z.string(), label: z.string() });

// A yes or no answer.
const booleanAnswer = z.strictObject({
	kind: z.literal('boolean'),
	...commonAnswerFields,
	default: z.boolean().optional()
});

// A text answer, optionally checked against a pattern. The pattern is compiled here so that a
// broken regular expression fails now instead of when the executor first checks an answer.
const stringAnswer = z.strictObject({
	kind: z.literal('string'),
	...commonAnswerFields,
	pattern: z
		.string()
		.refine(
			(pattern) => {
				try {
					new RegExp(pattern);
					return true;
				} catch {
					return false;
				}
			},
			{ message: 'Must be a valid regular expression' }
		)
		.optional(),
	normalise: z.enum(['upper_trim', 'lower_trim']).optional(),
	max_length: z.number().int().positive().optional(),
	default: z.string().optional()
});

// Choosing one or several options. The options are written out in full, or read at run time from a
// variable, where value_key and label_key name the fields to use from each item.
const selectAnswer = z
	.strictObject({
		kind: z.enum(['select_one', 'select_many']),
		...commonAnswerFields,
		options: z.array(optionItemSchema).min(1).optional(),
		options_from: variablePathSchema.optional(),
		value_key: z.string().min(1).optional(),
		label_key: z.string().min(1).optional(),
		default: z.union([z.string(), z.array(z.string())]).optional()
	})
	.refine((answer) => (answer.options !== undefined) !== (answer.options_from !== undefined), {
		message: 'Give either options or options_from, but not both and not neither'
	});

// An uploaded file. accept lists the file types allowed and max_bytes caps the size.
const fileAnswer = z.strictObject({
	kind: z.literal('file_ref'),
	...commonAnswerFields,
	accept: z.array(z.string().min(1)).min(1).optional(),
	max_bytes: z.number().int().positive().optional(),
	declared_only: z.boolean().optional()
});

export const answerDefinitionSchema = z.discriminatedUnion('kind', [
	booleanAnswer,
	stringAnswer,
	selectAnswer,
	fileAnswer
]);

// Moves the workflow on when the person does not answer in time, for example after a reminder.
export const inputTimeoutSchema = z.strictObject({
	after: durationOrRefSchema,
	next: stateRefSchema
});

// Asks one question and stores the answer in a variable before moving on.
export const inputStateSchema = z.strictObject({
	type: z.literal('input'),
	...stateCommonFields,
	prompt: z.string().min(1),
	schema: answerDefinitionSchema,
	assign: variablePathSchema,
	next: stateRefSchema,
	on_invalid: stateRefSchema.optional(),
	timeout: inputTimeoutSchema.optional()
});

export type AnswerDefinition = z.infer<typeof answerDefinitionSchema>;
export type InputTimeout = z.infer<typeof inputTimeoutSchema>;
export type InputState = z.infer<typeof inputStateSchema>;
