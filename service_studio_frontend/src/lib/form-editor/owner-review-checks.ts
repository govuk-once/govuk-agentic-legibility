import { processToGraph, visibleGraph } from '$lib/process-graph/process-to-graph';
import { stateRows, type StateRow } from '$lib/process-graph/state-rows';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { formHiddenStateTypes } from '$lib/form-editor/schema/form-states';

/*
	What the owner review shows about the form's journey and its checks. The real checks come from the tech review,
	which is not built yet, so until then the review can show example problems on the form's own steps. They let the
	design be seen with errors, warnings and a check that is still running, and they are switched on and off by hand.
*/

// How a step came out of its check: an error stops sign off, a warning does not, and pending means it is still running.
export type CheckResult = 'error' | 'warning' | 'pending';

export interface CheckProblem {
	result: CheckResult;
	stateId: string;
	message: string;
}

/**
 * Lists the steps of the form in the order and with the numbers the form editor gives them, so a step is called the
 * same thing in both. The hidden states, such as an assign, are left out, as they are in the editor until it is asked
 * to show them.
 */
export function journeySteps(process: WorkingProcess): StateRow[] {
	const graph = visibleGraph(processToGraph(process, formHiddenStateTypes), {
		showErrorRoutes: false,
		showDeveloperSteps: false
	});
	return stateRows(graph.nodes);
}

// Where each example problem goes, by its place in the list of steps, and what it says. The places follow the design.
const exampleChecks: { place: number; result: CheckResult; describe: (step: StateRow) => string }[] = [
	{
		place: 2,
		result: 'error',
		describe: (step) => `${step.title}, step ${step.number}: the answer is not saved anywhere, so no later step can use it`
	},
	{
		place: 3,
		result: 'warning',
		describe: (step) => `${step.title}, step ${step.number}: no related service. You can sign off with this`
	},
	{
		place: 5,
		result: 'pending',
		describe: (step) => `${step.title}, step ${step.number}: the check is still running. Come back in a few minutes`
	}
];

/**
 * Makes the example problems for a form's steps. A short form that has no step at one of the places gets fewer.
 */
export function exampleProblems(steps: StateRow[]): CheckProblem[] {
	return exampleChecks.flatMap(({ place, result, describe }) => {
		const step = steps[place];
		return step ? [{ result, stateId: step.stateId, message: describe(step) }] : [];
	});
}

/**
 * Counts the problems in words, such as "1 error, 1 warning, 1 pending", leaving out a kind there are none of.
 */
export function problemCount(problems: CheckProblem[]): string {
	const count = (result: CheckResult) => problems.filter((problem) => problem.result === result).length;
	const errors = count('error');
	const warnings = count('warning');
	const pending = count('pending');
	return [
		errors > 0 && `${errors} ${errors === 1 ? 'error' : 'errors'}`,
		warnings > 0 && `${warnings} ${warnings === 1 ? 'warning' : 'warnings'}`,
		pending > 0 && `${pending} pending`
	]
		.filter(Boolean)
		.join(', ');
}
