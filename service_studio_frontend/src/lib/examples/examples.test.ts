import { describe, expect, it } from 'vitest';
import { serviceExamples } from './index';

describe('bundled example services', () => {
	it('bundles at least one example', () => {
		expect(serviceExamples.length).toBeGreaterThan(0);
	});

	it('every bundled example validates against the canonical schema', () => {
		const failures = serviceExamples
			.filter((example) => example.service === null)
			.map((example) => ({ slug: example.slug, issues: example.issues }));

		expect(failures).toEqual([]);
	});
});
