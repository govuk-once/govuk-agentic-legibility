import { error } from '@sveltejs/kit';
import { serviceExamples } from '$lib/examples';
import type { PageLoad } from './$types';

// The examples are bundled and validated at build time, so resolving a slug needs no server round
// trip. A slug that matches no example, or one that failed validation, is a 404 rather than a page
// that tries to render a missing or broken service.
export const load: PageLoad = ({ params }) => {
	const example = serviceExamples.find((candidate) => candidate.slug === params.slug);
	if (!example?.service) error(404, 'Service not found');

	return { example: { slug: example.slug, name: example.name, service: example.service } };
};
