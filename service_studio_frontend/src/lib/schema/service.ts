import { z } from 'zod';

/*
	The canonical service schema from the RFC "Canonical Service Schema" (Sept 2nd 2026),
	transcribed into Zod v4.

	1. DateWindow.start and .end use z.iso.date() (a "YYYY-MM-DD" string) rather than the RFC's z.date().
	   Every source of a service definition, an LLM response, a stored file, a future editor save, hands
	   the validator JSON text, not a live Date object.
	2. Email, URL and UUID use the Zod v4 top level helpers z.email(), z.url() and z.uuid() rather than
	   the v3 z.string().email() style.
	3. startStepId must name a real step, every transition target must name a real step, every
	   endpoint response nextStepId must name a real step, and step ids must be unique.
	4. ServiceStep.performer and ServiceStep.window are optional. Fabricating
	   values to satisfy a required field would pollute the data.
	5. EndpointResponse.nextStepId is added. Real definitions use it to route on response status.
	   The graph only draws edges from a step's own transitions, so a definition that branches by
	   response status must also list each outcome as a transition.
	6. owner stays as an enum.
*/

/* Shared primitives */

const address = z.object({
	line1: z.string(),
	line2: z.string().optional(),
	town: z.string(),
	county: z.string().optional(),
	postcode: z.string(),
	// The schema assumes the United Kingdom where country is absent.
	country: z.string().optional()
});

const day = z.enum([
	'monday',
	'tuesday',
	'wednesday',
	'thursday',
	'friday',
	'saturday',
	'sunday',
	'bankHoliday'
]);

const openingPeriod = z.object({
	days: z.array(day),
	// 24 hour clock, for example "09:00".
	opens: z.string(),
	closes: z.string()
});

const openingTimes = z.object({
	periods: z.array(openingPeriod),
	notes: z.string().optional()
});

const dateWindow = z.object({
	start: z.iso.date(),
	end: z.iso.date()
});

const fieldOption = z.object({
	value: z.string(),
	label: z.string().optional()
});

const field = z.object({
	id: z.string(),
	// Should match the wallet or store key the value is read from or written to.
	name: z.string(),
	label: z.string(),
	element: z.enum(['text', 'email', 'number', 'date', 'textarea', 'select', 'checkbox', 'radio']),
	placeholder: z.string().optional(),
	hint: z.string().optional(),
	required: z.boolean().optional(),
	options: z.array(fieldOption).optional()
});

/* Ownership and document references */

const documentCategory = z.enum([
	'legislation',
	'policy',
	'guidance',
	'specification',
	'identity_proof',
	'address_proof',
	'financial_record',
	'qualification_or_certificate',
	'legal_instrument',
	'supporting_evidence',
	'other'
]);

const submissionMethod = z.enum(['upload', 'post', 'in_person', 'third_party_api']);

const documentReference = z.object({
	id: z.string().optional(),
	title: z.string(),
	category: documentCategory,
	issuer: z.string().optional(),
	reference: z.string().optional(),
	url: z.url().optional(),
	version: z.string().optional(),
	submissionMethod: z.array(submissionMethod).optional(),
	acceptedFormats: z.array(z.string()).optional(),
	maxAgeDays: z.number().int().positive().optional(),
	notes: z.string().optional()
});

/* Conditional logic primitives */

const comparisonOperator = z.enum([
	'equals',
	'notEquals',
	'contains',
	'greaterThan',
	'lessThan',
	'in'
]);

const rule = z.object({
	// Points to a Field.name or a data path.
	field: z.string(),
	operator: comparisonOperator,
	value: z.union([z.string(), z.number(), z.boolean(), z.array(z.string())])
});

const condition = z.object({
	all: z.array(rule).optional(),
	any: z.array(rule).optional()
});

const stepTransition = z.object({
	targetStepId: z.uuid(),
	// An omitted condition makes this the fallback or default path.
	condition: condition.optional(),
	label: z.string().optional()
});

/* Step types */

const dataType = z.enum(['string', 'number', 'integer', 'boolean', 'object', 'array', 'null']);

const bodyFormat = z.enum(['json', 'form', 'multipart', 'xml', 'text', 'binary']);

const header = z.object({
	name: z.string(),
	// Absent where the value is supplied at runtime, for example an authentication token injected by FLEX.
	value: z.string().optional(),
	required: z.boolean().optional(),
	description: z.string().optional()
});

const parameter = z.object({
	name: z.string(),
	in: z.enum(['path', 'query']),
	type: dataType,
	// Field.name or wallet key supplying the value.
	source: z.string().optional(),
	required: z.boolean().optional(),
	description: z.string().optional()
});

const bodyProperty = z.object({
	// Location within the body, for example "applicant.dateOfBirth".
	path: z.string(),
	type: dataType,
	source: z.string().optional(),
	required: z.boolean().optional(),
	description: z.string().optional()
});

const requestBody = z.object({
	format: bodyFormat,
	contentType: z.string(),
	properties: z.array(bodyProperty),
	schemaUrl: z.url().optional(),
	example: z.string().optional()
});

const endpointResponse = z.object({
	status: z.number().int(),
	description: z.string(),
	format: bodyFormat,
	contentType: z.string(),
	properties: z.array(bodyProperty),
	schemaUrl: z.url().optional(),
	example: z.string().optional(),
	// Deviation 5: route to this step when the call returns this status.
	nextStepId: z.uuid().optional()
});

const endpoint = z.object({
	kind: z.literal('endpoint'),
	method: z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']),
	url: z.url(),
	parameters: z.array(parameter),
	headers: z.array(header),
	// Absent where the method carries no body.
	request: requestBody.optional(),
	responses: z.array(endpointResponse),
	openApiUrl: z.url().optional(),
	operationId: z.string().optional()
});

const phone = z.object({
	kind: z.literal('phone'),
	number: z.string(),
	textphone: z.string().optional(),
	callCharges: z.string().optional(),
	openingTimes
});

const person = z.object({
	kind: z.literal('person'),
	location: address,
	appointmentRequired: z.boolean().optional(),
	openingTimes
});

const letter = z.object({
	kind: z.literal('letter'),
	address
});

const info = z.object({
	kind: z.literal('info'),
	// The heading is taken from ServiceStep.name. An empty body with fields is the indicator for a page that
	// only asks the citizen questions.
	body: z.string()
});

const stepType = z.discriminatedUnion('kind', [endpoint, phone, person, letter, info]);

/* Steps and services */

const serviceStep = z.object({
	id: z.uuid(),
	type: stepType,
	// Citizen facing. An info step uses this as its heading.
	name: z.string(),
	description: z.string(),
	// Deviation 4: optional.
	performer: z.string().optional(),
	// Deviation 4: optional.
	window: dateWindow.optional(),
	fields: z.array(field),
	// An empty array ends the journey at this step.
	transitions: z.array(stepTransition).default([])
});

/**
 * The full canonical service definition.  A definition that parses is also internally
 * consistent: every id it points at exists, and no two steps share an id.
 */
export const serviceSchema = z
	.object({
		id: z.uuid(),
		// Integer rather than a string based version.
		version: z.number().int(),
		state: z.enum(['draft', 'live', 'deprecated', 'retired']),
		name: z.string(),
		owner: z.enum(['gds', 'hmrc', 'dvla', 'dwp']),
		contact: z.email(),
		description: z.string(),
		descriptionPublic: z.string(),
		// Entry step into the journey graph.
		startStepId: z.uuid(),
		// Flat adjacency list of steps.
		steps: z.array(serviceStep)
	})
	.superRefine((service, ctx) => {
		// Collect every step id first so the reference checks below can look forward as well as back.
		const allIds = new Set<string>();
		for (const step of service.steps) {
			allIds.add(step.id);
		}

		// Report the second and later occurrence of any repeated id, since a duplicate makes every
		// reference to that id ambiguous.
		const seen = new Set<string>();
		service.steps.forEach((step, i) => {
			if (seen.has(step.id)) {
				ctx.addIssue({
					code: 'custom',
					path: ['steps', i, 'id'],
					message: `Duplicate step id "${step.id}"`
				});
			}
			seen.add(step.id);
		});

		if (!allIds.has(service.startStepId)) {
			ctx.addIssue({
				code: 'custom',
				path: ['startStepId'],
				message: `startStepId "${service.startStepId}" is not one of the step ids`
			});
		}

		service.steps.forEach((step, i) => {
			step.transitions.forEach((transition, j) => {
				if (!allIds.has(transition.targetStepId)) {
					ctx.addIssue({
						code: 'custom',
						path: ['steps', i, 'transitions', j, 'targetStepId'],
						message: `targetStepId "${transition.targetStepId}" is not one of the step ids`
					});
				}
			});

			if (step.type.kind === 'endpoint') {
				step.type.responses.forEach((response, k) => {
					if (response.nextStepId != null && !allIds.has(response.nextStepId)) {
						ctx.addIssue({
							code: 'custom',
							path: ['steps', i, 'type', 'responses', k, 'nextStepId'],
							message: `nextStepId "${response.nextStepId}" is not one of the step ids`
						});
					}
				});
			}
		});
	});

export type Service = z.infer<typeof serviceSchema>;
export type ServiceStep = z.infer<typeof serviceStep>;
export type StepTransition = z.infer<typeof stepTransition>;
export type Condition = z.infer<typeof condition>;
export type Field = z.infer<typeof field>;
export type ServiceStepKind = ServiceStep['type']['kind'];
