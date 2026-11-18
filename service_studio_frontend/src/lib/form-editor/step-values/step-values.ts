import { processToGraph, stateTitle } from '$lib/process-graph/process-to-graph';
import { noteOf, replaceState, withNote } from '$lib/schema/workflow/edit-state';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { formDeveloperStateTypes } from '../schema/form-states';

/*
	The developer steps of a form, as the step values stage of the technical review lists them. Each one is opened in
	turn, its values are checked and changed if needed, and it is marked as checked.
*/

/**
 * One developer step as the list shows it, with the state itself so its panel can fill in its fields.
 */
export interface DeveloperStep {
	code: string;
	title: string;
	state: WorkingState;
}

/**
 * Lists the developer steps of the form's main process in journey order, the same order the graph draws them in, so
 * the list reads from the start of the journey to the end.
 */
export function developerSteps(workflow: Workflow): DeveloperStep[] {
	const process = workflow.processes[workflow.manifest.entry];
	return processToGraph(process).nodes.flatMap((node): DeveloperStep[] => {
		if (node.type !== 'step') return [];
		const state = process.states[node.data.stateId];
		if (!state || !formDeveloperStateTypes.includes(state.state_type)) return [];
		return [{ code: node.data.stateId, title: stateTitle(state, node.data.stateId), state }];
	});
}

/**
 * Writes the main values of a developer step on one line, so the list shows what each step does without opening
 * it. The values are written as they are in the schema.
 */
export function stepValuesSummary(state: WorkingState): string {
	switch (state.state_type) {
		case 'api_call':
			return [state.method, state.service, ...(state.assign ? [`assign ${state.assign}`] : [])].join(' · ');
		case 'assign': {
			const variables = Object.keys(state.set);
			return variables.length === 1 ? `sets ${variables[0]}` : `sets ${variables.length} values`;
		}
		case 'wait':
			return typeof state.duration === 'string' ? state.duration : state.duration.$;
		default:
			return '';
	}
}

/**
 * Puts one changed state back into the form's main process. Every other state, and every other process, is kept as
 * it was.
 */
export function withEntryState(workflow: Workflow, code: string, state: WorkingState): Workflow {
	const processId = workflow.manifest.entry;
	// A step changed at the technical review keeps its next, so the process still matches the saved shape.
	const process = replaceState(workflow.processes[processId], code, state) as Workflow['processes'][string];
	return { ...workflow, processes: { ...workflow.processes, [processId]: process } };
}

/**
 * Something that must be put right before a step can be marked as checked. The field is the id of the input it is
 * about, so the error summary can link to it.
 */
export interface StepValueProblem {
	field: string;
	message: string;
}

// What reading a panel's fields gives: the step with its new values, or the problems that stop it being saved.
export type StepValuesResult<State> = { ok: true; state: State } | { ok: false; problems: StepValueProblem[] };

// The key in a developer step's notes that holds when the technical review that checked it was sent, so the owner
// review can tell the step has been checked.
export const techReviewCheckedKey = 'tech_review_checked_at';

/**
 * Writes the time the technical review was sent into the notes of every developer step, as an ISO 8601 date and time.
 * A time from an earlier review is replaced, because the step has been checked again.
 */
export function withTechReviewChecked(workflow: Workflow, sentAt: string): Workflow {
	return developerSteps(workflow).reduce(
		(changed, step) => withEntryState(changed, step.code, withNote(step.state, techReviewCheckedKey, sentAt)),
		workflow
	);
}

/**
 * Counts the developer steps and how many of them a sent technical review has checked, for the owner review.
 */
export function techReviewChecked(workflow: Workflow): { checked: number; total: number } {
	const steps = developerSteps(workflow);
	return { checked: steps.filter((step) => noteOf(step.state, techReviewCheckedKey) !== '').length, total: steps.length };
}
