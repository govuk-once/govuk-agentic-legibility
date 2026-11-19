import { z } from 'zod';
import { expressionSchema } from './expression';
import { durationOrRefSchema, metadataSchema, stateRefSchema, variablePathSchema } from './primitives';

/*
	The four simple states from sections 1.8, 1.11, 1.13 and 1.14 of the unified class structure
	document: output, assign, wait and end. Each is a strict object, so a key the document does not
	list is rejected.

	1. Every state accepts an optional name and metadata. The name
	   is the title shown to a person, and the metadata holds notes that only Service Studio reads at this time (future iterations of the executor may use some metadata).
	2. The document does not say which keys are required. A key is required here only when every
	   real example state includes it and the document gives no default for it.
	3. An output on the transcript channel needs a message, and an output on email or sms needs a
	   template, because the document says each channel reads a different one of the two.
	4. The return of an end state is a map of names to expressions, as the document says. A state that hands
	   nothing back leaves the key out, and null is refused.
*/

/**
 * The keys of the BaseState class in section 1.7 of the unified class structure document that every state
 * shares: the optional title and the notes. Each state schema spreads these in, so they are described once.
 * The document names the state type key state_type, as a field of BaseState. Each state gives it its own fixed value,
 * so it is written in each state schema and not here. A file may also say type, which is accepted when it is read.
 * See acceptTypeAlias in process.ts.
 */
export const baseStateFields = {
	name: z.string().min(1).optional(),
	metadata: metadataSchema.optional()
};

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

// Sets process variables. Each key is the variable to change and each value is an expression.
export const assignStateSchema = z.strictObject({
	state_type: z.literal('assign'),
	...baseStateFields,
	set: z.record(variablePathSchema, expressionSchema),
	next: stateRefSchema
});

// Pauses the workflow for a set time, for example between two checks of a remote service.
export const waitStateSchema = z.strictObject({
	state_type: z.literal('wait'),
	...baseStateFields,
	duration: durationOrRefSchema,
	next: stateRefSchema
});

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

export type OutputState = z.infer<typeof outputStateSchema>;
export type AssignState = z.infer<typeof assignStateSchema>;
export type WaitState = z.infer<typeof waitStateSchema>;
export type EndState = z.infer<typeof endStateSchema>;
export type CompletionStatus = z.infer<typeof completionStatusSchema>;
