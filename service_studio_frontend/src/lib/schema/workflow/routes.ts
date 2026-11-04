import type { State } from './process';

/*
	Every state can send the journey on in more than one place: next, a choice rule, a default, an
	invalid answer route, a timeout and the catch clauses. The checks and the graph both need that
	full list, so it is worked out here once and nothing else has to know which key holds a route.
*/

/**
 * One way out of a state. The target is the name of the state it leads to, and the path says where
 * in the state it was written, for example ["rules", 0, "next"], so an error can point at it. The
 * kind names the key the route belongs to, so the graph can tell a normal onward route from a
 * timeout or an error route without reading the path.
 */
export type Route = {
	target: string;
	path: (string | number)[];
	kind: 'next' | 'rule' | 'default' | 'on_invalid' | 'timeout' | 'catch';
};

// The kinds of route that deal with something going wrong or running late: a named error, a timeout
// and an invalid answer. They are kept in one list so the graph and the step numbers treat them alike.
const errorRouteKinds = new Set<string>(['catch', 'timeout', 'on_invalid']);

/**
 * Tells whether a kind of route is an error route. The graph hides these by default, and the step
 * numbers follow the main journey first, because several steps often lead to the same few end states
 * and the lines cross the main journey.
 */
export function isErrorKind(kind: string): boolean {
	return errorRouteKinds.has(kind);
}

/**
 * Lists every route out of a state, in the order they are written. An end state has none. The
 * switch covers each state type, so adding a new type without handling it here fails to compile.
 */
export function routesOf(state: State): Route[] {
	switch (state.type) {
		case 'end':
			return [];

		case 'choice':
			// Rules are listed first, in the order they are tested, and the default comes last.
			return [
				...state.rules.map((rule, index): Route => ({ target: rule.next, path: ['rules', index, 'next'], kind: 'rule' })),
				{ target: state.default, path: ['default'], kind: 'default' }
			];

		case 'input': {
			const routes: Route[] = [{ target: state.next, path: ['next'], kind: 'next' }];
			if (state.on_invalid) routes.push({ target: state.on_invalid, path: ['on_invalid'], kind: 'on_invalid' });
			if (state.timeout) routes.push({ target: state.timeout.next, path: ['timeout', 'next'], kind: 'timeout' });
			return routes;
		}

		case 'call':
		case 'invoke':
			// A call and an invoke both have a next state and can also route a named error elsewhere.
			return [
				{ target: state.next, path: ['next'], kind: 'next' },
				...(state.catch ?? []).map(
					(clause, index): Route => ({ target: clause.next, path: ['catch', index, 'next'], kind: 'catch' })
				)
			];

		case 'output':
		case 'assign':
		case 'wait':
			return [{ target: state.next, path: ['next'], kind: 'next' }];
	}
}
