import { apiCallStateSchema } from '$lib/schema/workflow/api-call-state';
import { isPlaceholderBodyValue } from '$lib/schema/workflow/placeholders';
import { variablePathSchema } from '$lib/schema/workflow/primitives';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { StepValueProblem, StepValuesResult } from './step-values';

/*
	The values of an API call step that are checked at the technical review: where it sends the request, what it
	sends, and where it saves the reply. The body is typed as JSON, as it is written in the schema.
*/

type WorkingApiCall = Extract<WorkingState, { state_type: 'api_call' }>;

// The methods a call can use, read from the schema so the buttons always match it.
export const apiCallMethods = apiCallStateSchema.shape.method.options;

/**
 * The values of an API call as they are typed in its panel. The body is the JSON text of the body, and empty when the
 * call sends none. Save reply as is empty when the reply is not saved under a name.
 */
export interface ApiCallValues {
	url: string;
	method: string;
	service: string;
	assign: string;
	body: string;
}

// The id of each field, which a problem names so the error summary can link to it.
export const apiCallFields: Record<keyof ApiCallValues, string> = {
	url: 'api-call-url',
	method: 'api-call-method',
	service: 'api-call-service',
	assign: 'api-call-assign',
	body: 'api-call-body'
};

/**
 * Reads the values of an API call into the text its panel shows. The body is set out over several lines so each
 * field sits on its own line.
 */
export function apiCallValuesOf(state: WorkingApiCall): ApiCallValues {
	return {
		url: state.url,
		method: state.method,
		service: state.service,
		assign: state.assign ?? '',
		body: state.body ? JSON.stringify(state.body, null, 2) : ''
	};
}

/**
 * Finds the first field of a body that sends a saved answer, written as JSON, so a hint or a problem can show the way
 * a saved answer is written using a real field of the call rather than a made up one. A placeholder left to fill in is
 * not a saved answer, so it is passed over. A body with no saved answers gives nothing.
 */
export function savedAnswerExample(body: WorkingApiCall['body']): { field: string; value: string } | undefined {
	const found = Object.entries(body ?? {}).find(
		([, value]) => typeof value === 'object' && value !== null && '$' in value && !isPlaceholderBodyValue(value)
	);
	return found && { field: JSON.stringify({ [found[0]]: found[1] }), value: JSON.stringify(found[1]) };
}

/**
 * Reads the typed body. Empty text means the call sends no body. Anything else must be a JSON object whose values the
 * schema accepts, and none of them may still be the placeholder a connected endpoint left for a field to fill in.
 */
function readBody(text: string, before: WorkingApiCall['body']): { body?: WorkingApiCall['body']; problem?: string } {
	if (text.trim() === '') return {};
	let parsed: unknown;
	try {
		parsed = JSON.parse(text);
	} catch {
		const example = savedAnswerExample(before);
		return { problem: example ? `Write the body as JSON, such as ${example.field}` : 'Write the body as JSON' };
	}
	const checked = apiCallStateSchema.shape.body.safeParse(parsed);
	if (!checked.success || checked.data === undefined) {
		return { problem: 'Write the body as a JSON object whose values are saved answers or fixed values' };
	}
	const unfilled = Object.entries(checked.data).find(([, value]) => isPlaceholderBodyValue(value));
	if (unfilled) return { problem: `Give ${unfilled[0]} a value in the body` };
	return { body: checked.data };
}

/**
 * Reads the typed values into the call. The url and service must be given. Save reply as is left out when it is
 * empty, and otherwise must be a name the schema accepts. The rest of the call, such as what it captures from the
 * reply, is kept as it was.
 */
export function apiCallWithValues(state: WorkingApiCall, values: ApiCallValues): StepValuesResult<WorkingApiCall> {
	const problems: StepValueProblem[] = [];
	const url = values.url.trim();
	const service = values.service.trim();
	const assign = values.assign.trim();
	const method = apiCallStateSchema.shape.method.safeParse(values.method);

	if (url === '') problems.push({ field: apiCallFields.url, message: 'Enter the url' });
	if (!method.success) problems.push({ field: apiCallFields.method, message: 'Choose a method' });
	if (service === '') problems.push({ field: apiCallFields.service, message: 'Enter the service' });
	if (assign !== '' && !variablePathSchema.safeParse(assign).success) {
		problems.push({ field: apiCallFields.assign, message: 'Enter where the reply is saved as a name such as submission, or leave it empty' });
	}
	const { body, problem } = readBody(values.body, state.body);
	if (problem) problems.push({ field: apiCallFields.body, message: problem });

	if (problems.length > 0 || !method.success) return { ok: false, problems };

	// The old body and save name are taken out, so an emptied field leaves the call without them.
	const { body: _oldBody, assign: _oldAssign, ...rest } = state;
	return {
		ok: true,
		state: { ...rest, url, method: method.data, service, ...(assign && { assign }), ...(body && { body }) }
	};
}
