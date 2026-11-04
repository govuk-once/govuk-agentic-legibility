import { describe, expect, it } from 'vitest';
import { assembleWorkflow, exampleFolders, workflowExamples } from '../workflows';

describe('assembleWorkflow', () => {
	const manifest = { id: 'a.b' };
	const files = {
		'workflow_manifest.json': manifest,
		'first.json': { process_id: 'first' },
		'second.json': { process_id: 'second' }
	};

	it('takes the manifest from its file name', () => {
		expect(assembleWorkflow(files).manifest).toBe(manifest);
	});

	it('keys every other file by its name without the .json ending', () => {
		expect(Object.keys(assembleWorkflow(files).processes)).toEqual(['first', 'second']);
	});

	it('leaves the manifest out of the processes', () => {
		expect(assembleWorkflow(files).processes).not.toHaveProperty('workflow_manifest');
	});

	it('leaves the manifest undefined when the folder has none, so validation reports it', () => {
		const { 'workflow_manifest.json': _removed, ...withoutManifest } = files;
		expect(assembleWorkflow(withoutManifest).manifest).toBeUndefined();
	});

	it('does not change the files it is given', () => {
		const before = JSON.stringify(files);
		assembleWorkflow(files);
		expect(JSON.stringify(files)).toBe(before);
	});
});

describe('exampleFolders', () => {
	it('groups the files of each example under its folder name', () => {
		expect(Object.keys(exampleFolders).sort()).toEqual(['change_of_address', 'maternity_allowance']);
		expect(exampleFolders.change_of_address).toHaveProperty('workflow_manifest.json');
		expect(exampleFolders.change_of_address).toHaveProperty('driver_details.json');
		expect(Object.keys(exampleFolders.maternity_allowance)).toHaveLength(7);
	});
});

describe('workflowExamples', () => {
	it('lists both example workflows in name order', () => {
		expect(workflowExamples.map((example) => example.slug)).toEqual(['change_of_address', 'maternity_allowance']);
	});

	it('validates every example with no errors', () => {
		const failures = workflowExamples
			.filter((example) => example.workflow === null)
			.map((example) => ({ slug: example.slug, issues: example.issues }));

		expect(failures).toEqual([]);
	});

	it('gives each valid example all the processes its manifest lists', () => {
		for (const example of workflowExamples) {
			const listed = example.workflow?.manifest.processes.map((process) => process.process_id).sort();
			expect(Object.keys(example.workflow?.processes ?? {}).sort()).toEqual(listed);
		}
	});

	it('carries the warnings of each example', () => {
		const warningCounts = Object.fromEntries(workflowExamples.map((example) => [example.slug, example.warnings.length]));
		expect(warningCounts).toEqual({ change_of_address: 0, maternity_allowance: 1 });
	});
});
