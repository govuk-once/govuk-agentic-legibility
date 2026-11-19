import { answerTypeKey, answerTypesByKind } from '$lib/form-editor/schema/answer-types';
import { isEditableInForm } from '$lib/form-editor/schema/form-states';
import { descriptionKey } from '$lib/schema/workflow/edit-state';
import type { Process } from '$lib/schema/workflow/process';
import type { Workflow } from '$lib/schema/workflow/workflow';
import { buildDraftWorkflow } from '../shared/build-draft-workflow';
import type { GenerationIssue } from '../shared/generate-json';
import type { OnboardDetails } from '../shared/onboard-details';

/*
	What a form draft needs beyond the wrapping every draft gets. A form has no calls, so it has no defaults for
	them and no error routes. Each question is given an answer type the app recognises, and a whole run is given
	the limit the existing forms use. The description of the manifest holds the name of the form, as it does in the
	existing forms, so the editor shows the form by its name, and what the person said the form does is kept as a
	note in the metadata of the manifest.
*/

// How long a whole run of a form may last before the executor stops it. Seven days is the limit the existing
// forms use. A real limit is set at the technical review.
export const formRunTimeout = 'P7D';

/**
 * Lists the states of a process that a form cannot have, which is every state a person cannot edit in the form
 * editor, such as a call or a wait. The model is told to leave them out, and this is where a reply that has one
 * is caught, so it can be sent back to be corrected.
 */
export function statesNotForForms(process: Process): GenerationIssue[] {
	return Object.entries(process.states).flatMap(([code, state]) =>
		isEditableInForm(state) ? [] : [{ path: `states.${code}.state_type`, message: `A form cannot have a state of type "${state.state_type}"` }]
	);
}

/**
 * Gives every question an answer type that goes with its kind of answer. One the model wrote is kept when it is
 * in the list for that kind. One that is missing, or is not in the list, becomes the first of the list, which is
 * the most general. A process whose questions all have one is returned as it is.
 */
export function withAnswerTypes(process: Process): Process {
	const typeFor = (state: Process['states'][string]) => {
		if (state.state_type !== 'input') return undefined;
		const allowed = answerTypesByKind[state.schema.kind];
		const written = state.metadata?.[answerTypeKey];
		return typeof written === 'string' && allowed.includes(written) ? undefined : allowed[0];
	};
	if (!Object.values(process.states).some(typeFor)) return process;

	const states = Object.fromEntries(
		Object.entries(process.states).map(([code, state]) => {
			const type = typeFor(state);
			return [code, type ? { ...state, metadata: { ...state.metadata, [answerTypeKey]: type } } : state];
		})
	);
	return { ...process, states };
}

/**
 * Wraps a generated process into a form workflow. Every question gets an answer type, and the manifest has no
 * defaults for calls and the run limit of a form. The manifest is described by the name of the form, and what the
 * form does is kept in the notes of the manifest. The process that is given in is never changed.
 */
export function buildForm(generated: Process, details: OnboardDetails): Workflow {
	const workflow = buildDraftWorkflow(withAnswerTypes(generated), details, { defaults: {}, runTimeout: formRunTimeout });

	// A note is only added when the person said what the form does, so an empty one is never saved.
	const purpose = details.description.trim();
	return {
		...workflow,
		manifest: { ...workflow.manifest, description: details.name, ...(purpose ? { metadata: { [descriptionKey]: purpose } } : {}) }
	};
}
