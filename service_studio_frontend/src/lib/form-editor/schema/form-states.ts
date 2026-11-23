import type { DraftLoad } from '$lib/draft-store';
import type { State } from '$lib/schema/workflow/process';
import type { WorkflowIssue } from '$lib/schema/workflow/validate';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import type { Workflow } from '$lib/schema/workflow/workflow';

/*
	What the form editor does with each kind of state. A form is mostly inputs and messages joined by decisions,
	so those are edited here, and so is the end. The other kinds may appear in a form, for example an assign that
	saves a repeated answer or an API call that submits the form, and they are shown but not edited. They are set by a
	developer at the technical review.

	Forms use the same schema as services, so nothing here refuses a kind of state. The one thing a form is not is a
	workflow of several processes, because the form editor opens a single process.
*/

export type FormStateAccess = 'editable' | 'read only';

// The record is keyed by every kind of state, so adding a kind to the schema without saying how a form treats it
// fails to compile.
export const formStateAccess: Record<State['state_type'], FormStateAccess> = {
	input: 'editable',
	output: 'editable',
	choice: 'editable',
	end: 'editable',
	assign: 'read only',
	wait: 'read only',
	invoke: 'read only',
	api_call: 'read only'
};

// The kinds of state that are developer steps in a form, which are set up at the technical review. An assign saves a
// repeated answer, an API call sends the form or checks on it, and a wait pauses before checking again.
export const formDeveloperStateTypes: readonly State['state_type'][] = ['assign', 'api_call', 'wait'];

// The developer steps that are drawn smaller and greyed on the graph, and hidden until the person asks to see
// developer states. An API call and a wait are shown as ordinary steps, because they change what the person goes
// through, while an assign only moves an answer from one place to another behind the scenes.
export const formHiddenStateTypes: readonly State['state_type'][] = ['assign'];

/**
 * Tells whether a person can change a state in the form editor. A read only state is shown with its values as text.
 */
export function isEditableInForm(state: WorkingState): boolean {
	return formStateAccess[state.state_type] === 'editable';
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

/**
 * Checks a form read from the browser tab. A form that matches the schema is also checked to be a single process,
 * and one that is not comes back with the problem, in the same way as one that does not match the schema.
 */
export function checkLoadedForm(loaded: DraftLoad): DraftLoad {
	if (!loaded.ok) return loaded;
	const issues = checkFormWorkflow(loaded.workflow);
	return issues.length > 0 ? { ok: false, reason: 'invalid', issues } : loaded;
}
