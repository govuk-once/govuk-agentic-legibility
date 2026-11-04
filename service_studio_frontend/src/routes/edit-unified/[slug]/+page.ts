import { error } from '@sveltejs/kit';
import { workflowExamples } from '$lib/examples/workflows';
import type { PageLoad } from './$types';

// The examples are bundled when the app is built, so finding one by its slug needs no server request.
// A slug that matches no example, or an example that failed validation, gives a 404 so the page never
// tries to draw a workflow that is missing or broken.
export const load: PageLoad = ({ params }) => {
	const example = workflowExamples.find((candidate) => candidate.slug === params.slug);
	if (!example?.workflow) error(404, 'Service not found');

	return { slug: example.slug, workflow: example.workflow };
};
