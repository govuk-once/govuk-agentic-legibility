import type { State } from './process';

/*
	Every state can send the journey on in more than one place: next, a choice rule, a default, an
	invalid answer route, a timeout and the catch clauses. The checks and the graph both need that
	full list, so it is worked out here once and nothing else has to know which key holds a route.
*/

/**
 * One way out of a state. The target is the name of the state it leads to, and the path says where
 * in the state it was written, for example ["rules", 0, "next"], so an error can point at it.
 */
export type Route = { target: string; path: (string | number)[] };

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
				...state.rules.map((rule, index) => ({ target: rule.next, path: ['rules', index, 'next'] })),
				{ target: state.default, path: ['default'] }
			];

		case 'input': {
			const routes: Route[] = [{ target: state.next, path: ['next'] }];
			if (state.on_invalid) routes.push({ target: state.on_invalid, path: ['on_invalid'] });
			if (state.timeout) routes.push({ target: state.timeout.next, path: ['timeout', 'next'] });
			return routes;
		}

		case 'call':
		case 'invoke':
			// A call and an invoke both have a next state and can also route a named error elsewhere.
			return [
				{ target: state.next, path: ['next'] },
				...(state.catch ?? []).map((clause, index) => ({ target: clause.next, path: ['catch', index, 'next'] }))
			];

		case 'output':
		case 'assign':
		case 'wait':
			return [{ target: state.next, path: ['next'] }];
	}
}
