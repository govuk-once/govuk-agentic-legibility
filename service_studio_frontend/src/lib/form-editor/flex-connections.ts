import { processToGraph, stateTitle } from '$lib/process-graph/process-to-graph';
import type { ApiCallState } from '$lib/schema/workflow/api-call-state';
import { isPlaceholderBodyValue, isUnconnectedApiCall, placeholderBodyValue } from '$lib/schema/workflow/placeholders';
import type { Workflow } from '$lib/schema/workflow/workflow';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { withEntryState } from '$lib/form-editor/step-values/step-values';

/*
	The Flex connections of a form. Every API call step has to be connected to a Flex endpoint before the form can be
	published, and connecting one fills in the call's method, service, url and the fields of its body. A call that still
	holds the placeholder details from when it was drawn is not connected yet.
*/

/**
 * One API call step as the Flex connections list shows it.
 */
export interface ApiCallStep {
	code: string;
	title: string;
	stateType: ApiCallState['state_type'];
	method: ApiCallState['method'];
	url: string;
	connected: boolean;
}

/**
 * An endpoint a call can be connected to, with the details it writes into the call and the words that say what it
 * does. A deprecated endpoint still works but is being replaced, so it is shown greyed out.
 */
export interface FlexEndpoint {
	method: ApiCallState['method'];
	service: string;
	url: string;
	description: string;
	// The names of the fields the endpoint expects in its body, as an OpenAPI request body lists them. An endpoint
	// that takes no body, such as one that only reads, leaves this out.
	bodyFields?: string[];
	deprecated?: boolean;
}

/**
 * How many fields a body has and how many of them still hold the placeholder value.
 */
export interface BodySummary {
	fields: number;
	toFillIn: number;
}


/**
 * Lists the API call steps of a process in journey order, the same order the graph draws them in, so the list reads
 * from the start of the journey to the end.
 */
export function apiCallSteps(process: WorkingProcess): ApiCallStep[] {
	return processToGraph(process).nodes.flatMap((node): ApiCallStep[] => {
		if (node.type !== 'step') return [];
		const state = process.states[node.data.stateId];
		if (state?.state_type !== 'api_call') return [];
		return [
			{
				code: node.data.stateId,
				title: stateTitle(state, node.data.stateId),
				stateType: state.state_type,
				method: state.method,
				url: state.url,
				connected: !isUnconnectedApiCall(state)
			}
		];
	});
}

/**
 * Counts the API call steps and how many of them are connected, for the owner review's summary.
 */
export function flexConnections(process: WorkingProcess): { connected: number; total: number } {
	const steps = apiCallSteps(process);
	return { connected: steps.filter((step) => step.connected).length, total: steps.length };
}

/**
 * Tells whether a call already holds an endpoint's details, so the endpoint it is connected to can be shown as
 * chosen when the page opens.
 */
export function usesEndpoint(call: Pick<ApiCallState, 'method' | 'service' | 'url'>, endpoint: FlexEndpoint): boolean {
	return call.method === endpoint.method && call.service === endpoint.service && call.url === endpoint.url;
}

/**
 * Builds the body a call sends once it is connected to an endpoint. The endpoint says which fields it expects, but not
 * which answers go into them, so a field the call already fills keeps its value and a new field is given the
 * placeholder to be filled in at the step values stage. A field the endpoint does not expect is left out, and an
 * endpoint that takes no body gives none.
 */
export function bodyForEndpoint(body: ApiCallState['body'], endpoint: FlexEndpoint): ApiCallState['body'] {
	if (!endpoint.bodyFields) return undefined;
	return Object.fromEntries(endpoint.bodyFields.map((field) => [field, body?.[field] ?? placeholderBodyValue]));
}

/**
 * Counts the fields of a body and how many still need a value, for the panel that shows what an endpoint fills in.
 */
export function summariseBody(body: NonNullable<ApiCallState['body']>): BodySummary {
	const values = Object.values(body);
	return { fields: values.length, toFillIn: values.filter(isPlaceholderBodyValue).length };
}

/**
 * Connects one API call step of the form's main process to an endpoint by writing in the endpoint's method, service,
 * url and body. Everything else on the step, such as where it saves the reply, is kept, because those belong to the
 * journey and are checked in the step values. A code that is not an API call leaves the form as it is.
 */
export function withEndpoint(workflow: Workflow, code: string, endpoint: FlexEndpoint): Workflow {
	const state = workflow.processes[workflow.manifest.entry]?.states[code];
	if (state?.state_type !== 'api_call') return workflow;
	// The old body is taken out so a call to an endpoint that takes no body is saved without one.
	const { body, ...rest } = state;
	const { method, service, url } = endpoint;
	const newBody = bodyForEndpoint(body, endpoint);
	return withEntryState(workflow, code, { ...rest, method, service, url, ...(newBody && { body: newBody }) });
}
