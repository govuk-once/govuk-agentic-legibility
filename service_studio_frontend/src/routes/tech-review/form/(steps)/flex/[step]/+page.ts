import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { stateTitle } from '$lib/process-graph/process-to-graph';
import type { PageLoad } from './$types';

/**
 * Finds the API call step named in the address. A name that is not an API call in this form, such as one from an old
 * link, goes back to the list of Flex connections, where every call that can be connected is listed.
 */
export const load: PageLoad = async ({ parent, params }) => {
	const { workflow } = await parent();
	const state = workflow.processes[workflow.manifest.entry]?.states[params.step];
	if (state?.state_type !== 'api_call') redirect(307, resolve('/tech-review/form/flex'));
	return {
		call: { code: params.step, title: stateTitle(state, params.step), method: state.method, service: state.service, url: state.url, body: state.body }
	};
};
