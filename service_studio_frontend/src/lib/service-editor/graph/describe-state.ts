import type { WorkingState } from '$lib/schema/workflow/working-process';
import { routesOf, type Route } from '$lib/schema/workflow/routes';
import { describeCondition, describeDuration, describeExpression } from '$lib/process-graph/describe-value';
import { tidyCode } from '$lib/graph-kit/tidy-code';

/**
 * One fact about a state shown in the panel, such as the question an input asks. Both parts are text, so
 * the panel can list every kind of state in the same way. A main fact is the one thing that explains what
 * the state does and is always shown. The others are kept behind a fold, so the panel stays short.
 */
export type StateFact = { label: string; value: string; main?: boolean };

/**
 * One way out of a state, in words. The label says when the route is taken, such as "Otherwise" or
 * "If the answer is not valid", and the target says where it leads. The kind is kept so the panel can
 * leave out error routes while the graph hides them.
 */
export type StateRouteDescription = { label: string; kind: Route['kind']; targetId: string; targetTitle: string };

export type StateDescription = {
	code: string;
	// The schema's own name for the type of state, such as input or invoke.
	stateType: WorkingState['type'];
	facts: StateFact[];
	routes: StateRouteDescription[];
	// Set only on an invoke state, so the panel can offer to open the process it runs.
	opensProcess?: { id: string; title: string };
};

/**
 * Lists the facts a person needs to understand what a state does. Each type of state has its own list,
 * and the switch covers every type, so adding a state type without handling it here fails to compile.
 */
function factsOf(state: WorkingState): StateFact[] {
	switch (state.type) {
		case 'input': {
			const options = state.schema.kind === 'select_one' || state.schema.kind === 'select_many' ? state.schema.options : undefined;
			return [
				{ label: 'Question', value: state.prompt, main: true },
				{ label: 'Answer type', value: state.schema.kind },
				...(options ? [{ label: 'Choices', value: options.map((option) => option.label).join(', ') }] : []),
				{ label: 'Saved as', value: state.assign }
			];
		}

		case 'output':
			return [
				{ label: 'Channel', value: state.channel },
				...(state.message !== undefined ? [{ label: 'Message', value: state.message, main: true }] : []),
				...(state.template !== undefined ? [{ label: 'Template', value: state.template, main: true }] : [])
			];

		case 'api_call':
			return [
				{ label: 'Request', value: `${state.method} ${state.service}${state.url}`, main: true },
				...(state.assign ? [{ label: 'Response saved as', value: state.assign }] : []),
				...(state.capture ? [{ label: 'Keeps', value: Object.keys(state.capture).join(', ') }] : [])
			];

		case 'choice':
			// The rules are shown with the routes, because each rule is a route out of the state.
			return [];

		case 'assign':
			return Object.entries(state.set).map(([path, expression]) => ({ label: `Sets ${path}`, value: describeExpression(expression), main: true }));

		case 'invoke':
			return [
				{ label: 'Runs process', value: tidyCode(state.process) },
				...Object.entries(state.input ?? {}).map(([path, expression]) => ({
					label: `Passes in ${path}`,
					value: describeExpression(expression)
				})),
				...(state.assign ? [{ label: 'Result saved as', value: state.assign }] : [])
			];

		case 'wait':
			return [{ label: 'Waits for', value: describeDuration(state.duration), main: true }];

		case 'end':
			return [
				{ label: 'Finishes as', value: state.status, main: true },
				...(state.outcome ? [{ label: 'Outcome', value: state.outcome }] : []),
				...(state.return !== undefined ? [{ label: 'Returns', value: describeExpression(state.return) }] : [])
			];
	}
}

/**
 * Says when a route is taken. The route's kind says which key it came from, and the path inside the
 * state says which rule or error clause, so the words can quote the rule or the error name.
 */
function routeLabel(state: WorkingState, route: Route): string {
	switch (route.kind) {
		case 'next':
			return 'Next';
		case 'default':
			return 'Otherwise';
		case 'on_invalid':
			return 'If the answer is not valid';
		case 'timeout':
			return state.type === 'input' ? `If there is no answer after ${describeDuration(state.timeout?.after ?? '')}` : 'If it takes too long';
		case 'rule':
			return state.type === 'choice' ? `If ${describeCondition(state.rules[Number(route.path[1])].when)}` : 'If a rule matches';
		case 'catch': {
			if (state.type !== 'api_call' && state.type !== 'invoke') return 'If it goes wrong';
			const clause = state.catch?.[Number(route.path[1])];
			if (!clause || clause.on === 'any') return 'If anything goes wrong';
			return state.type === 'api_call' ? `If the call fails with ${clause.on}` : `If the process ends with ${clause.on}`;
		}
	}
}

/**
 * Describes one state in words for the read only panel: what it does and where it can lead. The title of
 * each target is looked up by the caller, because a title can come from a name, a question or a code and
 * the caller already works that out for the graph. A target that does not exist is named as missing.
 */
export function describeState(state: WorkingState, code: string, titleOf: (code: string) => string | undefined): StateDescription {
	return {
		code,
		stateType: state.type,
		facts: factsOf(state),
		routes: routesOf(state).map((route) => ({
			label: routeLabel(state, route),
			kind: route.kind,
			targetId: route.target,
			targetTitle: titleOf(route.target) ?? `${route.target} (missing)`
		})),
		opensProcess: state.type === 'invoke' ? { id: state.process, title: tidyCode(state.process) } : undefined
	};
}
