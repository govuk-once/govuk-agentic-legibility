import { parseService } from '$lib/schema';
import type { Service, ServiceIssue } from '$lib/schema';

// import.meta.glob eagerly bundles every example JSON at build time, so the /edit dropdown can list them
// without a server round trip. Each file is validated here, so a file that does not match the canonical
// schema still appears in the dropdown but renders its errors rather than a graph.
const modules = import.meta.glob('./*.json', { eager: true, import: 'default' });

export type ServiceExample = {
	slug: string;
	name: string;
	service: Service | null;
	issues: ServiceIssue[];
};

export const serviceExamples: ServiceExample[] = Object.entries(modules)
	.map(([path, raw]) => {
		const slug = path.replace(/^\.\//, '').replace(/\.json$/, '');
		const result = parseService(raw);
		return result.ok
			? { slug, name: result.service.name, service: result.service, issues: [] }
			: { slug, name: slug, service: null, issues: result.issues };
	})
	// Smallest journeys first so the dropdown opens on a graph that reads at a glance, with the large
	// worked examples after them. Anything that failed validation sorts to the end.
	.sort((a, b) => {
		const size = (example: ServiceExample) => example.service?.steps.length ?? Number.POSITIVE_INFINITY;
		return size(a) - size(b) || a.name.localeCompare(b.name);
	});
