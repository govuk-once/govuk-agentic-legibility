import { describe, expect, it } from 'vitest';
import { serviceExampleFolders, serviceExamples } from '../services';

describe('serviceExampleFolders', () => {
	it('groups the files of each example under its folder name', () => {
		expect(Object.keys(serviceExampleFolders).sort()).toEqual(['change_of_address', 'maternity_allowance']);
		expect(serviceExampleFolders.change_of_address).toHaveProperty('workflow_manifest.json');
		expect(serviceExampleFolders.change_of_address).toHaveProperty('driver_details.json');
		expect(Object.keys(serviceExampleFolders.maternity_allowance)).toHaveLength(7);
	});
});

describe('serviceExamples', () => {
	it('lists both example services in name order', () => {
		expect(serviceExamples.map((example) => example.slug)).toEqual(['change_of_address', 'maternity_allowance']);
	});

	it('validates every example with no errors', () => {
		const failures = serviceExamples
			.filter((example) => example.workflow === null)
			.map((example) => ({ slug: example.slug, issues: example.issues }));

		expect(failures).toEqual([]);
	});

	it('gives each valid example all the processes its manifest lists', () => {
		for (const example of serviceExamples) {
			const listed = example.workflow?.manifest.processes.map((process) => process.process_id).sort();
			expect(Object.keys(example.workflow?.processes ?? {}).sort()).toEqual(listed);
		}
	});

	it('carries the warnings of each example', () => {
		const warningCounts = Object.fromEntries(serviceExamples.map((example) => [example.slug, example.warnings.length]));
		expect(warningCounts).toEqual({ change_of_address: 0, maternity_allowance: 1 });
	});
});
