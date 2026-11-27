import { z } from 'zod';
import { baseStateFields } from '$lib/schema/workflow/states';

// Pauses the workflow for a set time, for example between two checks of a remote service.
export const waitStateSchema = z.strictObject({
	state_type: z.literal('wait'),
	...baseStateFields,
	duration: durationOrRefSchema,
	next: stateRefSchema
});


export type WaitState = z.infer<typeof waitStateSchema>;
