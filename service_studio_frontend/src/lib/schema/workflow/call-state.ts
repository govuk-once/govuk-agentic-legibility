import { z } from 'zod';
import { expressionSchema } from './expression';
import { stateCommonFields } from './states';
import { durationSchema, dynamicRefSchema, stateRefSchema, variablePathSchema } from './primitives';

/*
	The call state from section 1.9 of the unified class structure document, with the timeouts (1.4),
	retry policy (1.5), catch clause (2.6) and capture specification (2.7) it uses. The timeouts and
	retry policy are also used by the workflow defaults, so they are exported.

	1. The document does not say which call keys are required. A call needs a method, a service, a
	   url and a next state, because every example call has them and the call cannot run without
	   them. The rest are optional.
	2. Every key of timeouts and retry is optional, because the document says a call may override
	   the defaults, and an override can reasonably change one value only.
	3. A call has no required body, as a GET request has none.
*/

// How long a call may take. Each limit is a duration such as "PT15S".
export const timeoutsSchema = z.strictObject({
	start_to_close: durationSchema.optional(),
	schedule_to_close: durationSchema.optional(),
	heartbeat: durationSchema.optional()
});

// How a failed call is tried again. retry_on names the kinds of failure that are worth retrying.
export const retryPolicySchema = z.strictObject({
	max_attempts: z.number().int().positive().optional(),
	initial_interval: durationSchema.optional(),
	backoff_coefficient: z.number().positive().optional(),
	max_interval: durationSchema.optional(),
	retry_on: z.array(z.enum(['5xx', '429', 'timeout', 'connection'])).min(1).optional()
});

// Sends the workflow to another state when the call or sub process reports a named error. The name
// "any" matches every error. The invoke state uses this schema too.
export const catchClauseSchema = z.strictObject({
	on: z.string().min(1),
	next: stateRefSchema
});

// Says which part of the response to keep. A plain string is a path into the response. The longer
// form can also trim a list or a long piece of text.
export const captureSpecSchema = z.union([
	z.string().min(1),
	z.strictObject({
		from: z.string().min(1),
		pick: z.array(z.string().min(1)).optional(),
		max_items: z.number().int().positive().optional(),
		max_length: z.number().int().positive().optional()
	})
]);

// Calls an HTTP service. The service name is turned into a real address when the workflow runs.
export const callStateSchema = z.strictObject({
	type: z.literal('call'),
	...stateCommonFields,
	method: z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']),
	service: z.string().min(1),
	url: z.string().min(1),
	headers: z.record(z.string(), z.string()).optional(),
	body: z.record(z.string(), expressionSchema).optional(),
	source_ref: dynamicRefSchema.optional(),
	encoding: z.string().min(1).optional(),
	idempotency_key: z.string().min(1).optional(),
	timeouts: timeoutsSchema.optional(),
	retry: retryPolicySchema.optional(),
	assign: variablePathSchema.optional(),
	capture: z.record(variablePathSchema, captureSpecSchema).optional(),
	catch: z.array(catchClauseSchema).optional(),
	next: stateRefSchema
});

export type Timeouts = z.infer<typeof timeoutsSchema>;
export type RetryPolicy = z.infer<typeof retryPolicySchema>;
export type CatchClause = z.infer<typeof catchClauseSchema>;
export type CaptureSpec = z.infer<typeof captureSpecSchema>;
export type CallState = z.infer<typeof callStateSchema>;
