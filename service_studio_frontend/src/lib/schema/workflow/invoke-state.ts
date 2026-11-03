import { z } from 'zod';
import { catchClauseSchema } from './call-state';
import { expressionSchema } from './expression';
import { stateCommonFields } from './states';
import { processRefSchema, stateRefSchema, variablePathSchema } from './primitives';

/*
	The invoke state from section 1.12 of the unified class structure document. It runs another
	process, such as one section of a long service, and continues when that process ends.

	1. The document does not say which keys are required. The process and the next state are
	   required, and the rest are optional, because some example invokes pass nothing in or keep
	   nothing back.
	2. The catch names are meant to match the outcome names of the sub process's end states, as the
	   example workflows do. That link is checked across processes later, not here.
*/

// Runs the named process. input gives it its starting values, assign keeps what it returns, and
// catch routes the named ways it can end to other states.
export const invokeStateSchema = z.strictObject({
	type: z.literal('invoke'),
	...stateCommonFields,
	process: processRefSchema,
	input: z.record(variablePathSchema, expressionSchema).optional(),
	assign: variablePathSchema.optional(),
	catch: z.array(catchClauseSchema).optional(),
	next: stateRefSchema
});

export type InvokeState = z.infer<typeof invokeStateSchema>;
