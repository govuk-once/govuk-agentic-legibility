import { describe, expect, it } from 'vitest';
import { formExampleFolders, formExamples } from '../forms';

describe('formExampleFolders', () => {
	it('has a folder for each of the 14 forms, each holding a manifest and one process file', () => {
		expect(Object.keys(formExampleFolders)).toHaveLength(14);
		for (const [name, files] of Object.entries(formExampleFolders)) {
			const fileNames = Object.keys(files);
			expect(fileNames, name).toHaveLength(2);
			expect(fileNames, name).toContain('workflow_manifest.json');
		}
	});

	it('names the process file of each form after the form', () => {
		for (const [name, files] of Object.entries(formExampleFolders)) expect(Object.keys(files), name).toContain(`${name}.json`);
	});
});

describe('formExamples', () => {
	it('lists the forms in name order', () => {
		const slugs = formExamples.map((example) => example.slug);
		expect(slugs).toEqual([...slugs].sort((a, b) => a.localeCompare(b)));
		expect(slugs).toHaveLength(14);
	});

	it('validates every form with no errors and no warnings', () => {
		const problems = formExamples
			.filter((example) => example.workflow === null || example.warnings.length > 0)
			.map((example) => ({ slug: example.slug, issues: example.issues, warnings: example.warnings }));

		expect(problems).toEqual([]);
	});

	it('gives each form all the processes its manifest lists', () => {
		for (const example of formExamples) {
			const listed = example.workflow?.manifest.processes.map((process) => process.process_id).sort();
			expect(Object.keys(example.workflow?.processes ?? {}).sort(), example.slug).toEqual(listed);
		}
	});
});
