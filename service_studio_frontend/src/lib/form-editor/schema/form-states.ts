import type { State } from '$lib/schema/workflow/process';
import type { WorkflowIssue } from '$lib/schema/workflow/validate';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	What the form editor does with each kind of state. A form is mostly questions and messages joined by decisions,
	so those are edited here, and so is the end. The other kinds may appear in a form, for example an assign that
	saves a repeated answer or an API call that submits the form, and they are shown but not edited. They are set by a
	developer at the technical review.

	Forms use the same schema as services, so nothing here refuses a kind of state. The one thing a form is not is a
	workflow of several processes, because the form editor opens a single process.
*/

export type FormStateAccess = 'editable' | 'read only';

// The record is keyed by every kind of state, so adding a kind to the schema without saying how a form treats it
// fails to compile.
export const formStateAccess: Record<State['type'], FormStateAccess> = {
	input: 'editable',
	output: 'editable',
	choice: 'editable',
	end: 'editable',
	assign: 'read only',
	wait: 'read only',
	invoke: 'read only',
	api_call: 'read only'
};

// The kinds of state that are developer steps in a form. They are drawn smaller and greyed, and are hidden until the
// person asks to see developer steps. More kinds can be added here when they are too technical for most people.
export const formDeveloperStateTypes: readonly State['type'][] = ['assign'];

/**
 * Tells whether a person can change a state in the form editor. A read only state is shown with its values as text.
 */
export function isEditableInForm(state: WorkingState): boolean {
	return formStateAccess[state.type] === 'editable';
}

/**
 * Checks that a workflow is one the form editor can open. A form is a single process, so a workflow that lists
 * several, such as one with sections, cannot be edited here. An empty list means the form editor can open it.
 */
export function checkFormWorkflow(workflow: Pick<Workflow, 'manifest'>): WorkflowIssue[] {
	const count = workflow.manifest.processes.length;
	if (count === 1) return [];

	return [
		{
			path: 'manifest.processes',
			message: `A form is one process, but this workflow lists ${count}. The form editor opens a single process.`
		}
	];
}
