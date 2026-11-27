import { z } from 'zod';
import { baseStateFields } from '$lib/schema/workflow/states';

// How a process finished. The executor and the graph both read this to tell success from a failure.
export const completionStatusSchema = z.enum(['success', 'cancelled', 'failed', 'offramp', 'needs_attention']);

// Finishes the process. A sub process hands its return value back to the state that invoked it.
export const endStateSchema = z.strictObject({
	state_type: z.literal('end'),
	...baseStateFields,
	status: completionStatusSchema,
	outcome: z.string().min(1).optional(),
	return: z.record(z.string(), expressionSchema).optional()
});

export type CompletionStatus = z.infer<typeof completionStatusSchema>;
export type EndState = z.infer<typeof endStateSchema>;
