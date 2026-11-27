import { z } from 'zod';
import { baseStateFields } from '$lib/schema/workflow/states';


// Sets process variables. Each key is the variable to change and each value is an expression.
export const assignStateSchema = z.strictObject({
	state_type: z.literal('assign'),
	...baseStateFields,
	set: z.record(variablePathSchema, expressionSchema),
	next: stateRefSchema
});


export type AssignState = z.infer<typeof assignStateSchema>;
