import { error } from '@sveltejs/kit';
import { formExamples } from '$lib/examples/forms';
import { checkFormWorkflow } from '$lib/form-editor/schema/form-states';
import type { PageLoad } from './$types';

// The examples are bundled when the app is built, so finding one by its slug needs no server request. A slug that
// matches no example, an example that failed validation, or a workflow that is not a single process gives an error
// page, so the editor never tries to draw something it cannot open.
export const load: PageLoad = ({ params }) => {
	const example = formExamples.find((candidate) => candidate.slug === params.slug);
	if (!example?.workflow) error(404, 'Form not found');

	const [problem] = checkFormWorkflow(example.workflow);
	if (problem) error(422, problem.message);

	return { slug: example.slug, workflow: example.workflow };
};
