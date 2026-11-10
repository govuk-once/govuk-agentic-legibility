import { uniqueStateCode } from '$lib/schema/workflow/edit-process';
import {
	placeholderApiCallDefaults,
	placeholderExecutor,
	placeholderFailedEnd,
	placeholderNamespace,
	placeholderOwner
} from '$lib/schema/workflow/placeholders';
import type { Process } from '$lib/schema/workflow/process';
import { currentSchemaVersion, type Workflow } from '$lib/schema/workflow/workflow';
import { firstVersion, isWebAddress, slugOf, type OnboardDetails } from '../shared/onboard-details';

/*
	Wraps the process that the model generated into a whole workflow that the editor can open. The model is only
	asked for the journey itself. Everything else is decided here, because the model has no way of knowing it and
	a guess would look like a real value: the ids, the owner, the timeouts and the routes taken when a call fails.
	Each of those is a placeholder that a person replaces at a later review, and each is a valid value, so the
	workflow can be checked and opened straight away.
*/


/**
 * Gives every call that has no error route one that leads to a shared failed end, and adds that end. A call that
 * already says where its errors go is left alone, and a process with no such call is returned as it is. The error
 * route is added here and not by the model, because where an error should lead depends on the real service.
 */
export function withFailureRoutes(process: Process): Process {
	const needsRoute = (state: Process['states'][string]) => state.type === 'api_call' && !state.catch?.length;
	if (!Object.values(process.states).some(needsRoute)) return process;

	// The end is named after the states that are already there, so it cannot replace one of them.
	const endCode = uniqueStateCode(process, 'end_failed');
	const states = Object.fromEntries(
		Object.entries(process.states).map(([code, state]) => [
			code,
			state.type === 'api_call' && needsRoute(state) ? { ...state, catch: [{ on: 'any', next: endCode }] } : state
		])
	);

	return { ...process, states: { ...states, [endCode]: placeholderFailedEnd } };
}

/**
 * Wraps a generated process into a workflow with a manifest. The process is given the id and version that the
 * manifest lists, the links the person gave become its sources, and every call gets the placeholder error route.
 * The manifest holds the placeholders for the owner, the executor settings and the call defaults. The process
 * that is given in is never changed.
 */
export function buildWorkflow(generated: Process, details: OnboardDetails): Workflow {
	const slug = slugOf(details.name);
	const links = details.links.filter(isWebAddress);

	// The process takes its id from the name of the service, and the links the person gave are its sources. When no
	// usable link was given, whatever sources the process already had are kept.
	const process = withFailureRoutes({
		...generated,
		process_id: slug,
		version: firstVersion,
		...(links.length > 0 ? { source: links } : {})
	});

	return {
		manifest: {
			workflow_id: slug,
			schema: currentSchemaVersion,
			id: `${placeholderNamespace}.${slug}`,
			version: firstVersion,
			...placeholderOwner,
			description: details.description,
			state: 'draft',
			entry: slug,
			executor: placeholderExecutor(slug),
			defaults: { api_call: placeholderApiCallDefaults },
			processes: [{ process_id: slug, version: firstVersion }]
		},
		processes: { [slug]: process }
	};
}
