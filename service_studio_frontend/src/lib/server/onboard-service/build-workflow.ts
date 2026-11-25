import { uniqueStateCode } from '$lib/schema/workflow/edit-process';
import { placeholderApiCallDefaults, placeholderFailedEnd, placeholderRunTimeout } from '$lib/schema/workflow/placeholders';
import type { Process } from '$lib/schema/workflow/process';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { buildDraftWorkflow } from '../shared/build-draft-workflow';
import type { OnboardDetails } from '../shared/onboard-details';

/*
	What a service draft needs beyond the wrapping every draft gets: the routes taken when a call fails, and the
	time limit and retry policy its calls use. Like the rest of the wrapping they are placeholders, because where
	an error should lead and how long a call may take depend on the real service.
*/

/**
 * Gives every call that has no error route one that leads to a shared failed end, and adds that end. A call that
 * already says where its errors go is left alone, and a process with no such call is returned as it is. The error
 * route is added here and not by the model, because where an error should lead depends on the real service.
 */
export function withFailureRoutes(process: Process): Process {
	const needsRoute = (state: Process['states'][string]) => state.state_type === 'api_call' && !state.catch?.length;
	if (!Object.values(process.states).some(needsRoute)) return process;

	// The end is named after the states that are already there, so it cannot replace one of them.
	const endCode = uniqueStateCode(process, 'end_failed');
	const states = Object.fromEntries(
		Object.entries(process.states).map(([code, state]) => [
			code,
			state.state_type === 'api_call' && needsRoute(state) ? { ...state, catch: [{ on: 'any', next: endCode }] } : state
		])
	);

	return { ...process, states: { ...states, [endCode]: placeholderFailedEnd } };
}

/**
 * Wraps a generated process into a service workflow. Every call gets the placeholder error route, and the
 * manifest holds the placeholder defaults for calls and the run limit of a service. The process that is given in
 * is never changed.
 */
export function buildWorkflow(generated: Process, details: OnboardDetails): Workflow {
	return buildDraftWorkflow(withFailureRoutes(generated), details, {
		defaults: { api_call: placeholderApiCallDefaults },
		runTimeout: placeholderRunTimeout
	});
}
