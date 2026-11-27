import { z } from 'zod';
import { baseStateFields } from '$lib/schema/workflow/states';

// Emits a message to the person or sends a notification. A new person facing step is usually this.
export const outputStateSchema = z
	.strictObject({
		state_type: z.literal('output'),
		...baseStateFields,
		channel: z.enum(['transcript', 'email', 'sms']),
		message: z.string().optional(),
		template: z.string().optional(),
		params: z.record(z.string(), expressionSchema).optional(),
		idempotency_key: z.string().optional(),
		also_transcript: z.string().optional(),
		on_error: z.enum(['continue', 'fail']).optional(),
		next: stateRefSchema
	})
	.superRefine((state, context) => {
		// The transcript channel prints the message, while email and sms fill a named template.
		if (state.channel === 'transcript' && state.message === undefined) {
			context.addIssue({ code: 'custom', path: ['message'], message: 'A transcript output needs a message' });
		}
		if (state.channel !== 'transcript' && state.template === undefined) {
			context.addIssue({ code: 'custom', path: ['template'], message: 'An email or sms output needs a template' });
		}
	});

export type OutputState = z.infer<typeof outputStateSchema>;
