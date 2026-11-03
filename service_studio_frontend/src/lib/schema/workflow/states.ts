import { z } from 'zod';
import { expressionSchema } from './expression';
import { durationOrRefSchema, metadataSchema, stateRefSchema, variablePathSchema } from './primitives';

/*
	The four simple states from sections 1.8, 1.11, 1.13 and 1.14 of the unified class structure
	document: output, assign, wait and end. Each is a strict object, so a key the document does not
	list is rejected.

	1. Every state accepts an optional name and metadata, as agreed with the executor team. The name
	   is the title shown to a person, and the metadata holds notes that only Service Studio and the
	   channels read.
	2. The document does not say which keys are required. A key is required here only when every
	   real example state includes it and the document gives no default for it.
	3. An output on the transcript channel needs a message, and an output on email or sms needs a
	   template, because the document says each channel reads a different one of the two.
*/

/**
 * The keys that every state type shares. Each state schema spreads these in, so the optional title
 * and notes are described once.
 */
export const stateCommonFields = {
	name: z.string().min(1).optional(),
	metadata: metadataSchema.optional()
};

// Emits a message to the person or sends a notification. A new person facing step is usually this.
export const outputStateSchema = z
	.strictObject({
		type: z.literal('output'),
		...stateCommonFields,
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

// Sets process variables. Each key is the variable to change and each value is an expression.
export const assignStateSchema = z.strictObject({
	type: z.literal('assign'),
	...stateCommonFields,
	set: z.record(variablePathSchema, expressionSchema),
	next: stateRefSchema
});

// Pauses the workflow for a set time, for example between two checks of a remote service.
export const waitStateSchema = z.strictObject({
	type: z.literal('wait'),
	...stateCommonFields,
	duration: durationOrRefSchema,
	next: stateRefSchema
});

// How a process finished. The executor and the graph both read this to tell success from a failure.
export const completionStatusSchema = z.enum(['success', 'cancelled', 'failed', 'offramp', 'needs_attention']);

// Finishes the process. A sub process hands its return value back to the state that invoked it.
export const endStateSchema = z.strictObject({
	type: z.literal('end'),
	...stateCommonFields,
	status: completionStatusSchema,
	outcome: z.string().min(1).optional(),
	return: expressionSchema.optional()
});

export type OutputState = z.infer<typeof outputStateSchema>;
export type AssignState = z.infer<typeof assignStateSchema>;
export type WaitState = z.infer<typeof waitStateSchema>;
export type EndState = z.infer<typeof endStateSchema>;
export type CompletionStatus = z.infer<typeof completionStatusSchema>;
