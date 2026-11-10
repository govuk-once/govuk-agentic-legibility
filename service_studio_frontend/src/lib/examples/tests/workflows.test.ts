import { describe, expect, it } from 'vitest';
import { assembleWorkflow, groupByFolder, loadExamples } from '../workflows';

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

describe('groupByFolder', () => {
	it('groups files by the folder and file name at the end of their path', () => {
		const grouped = groupByFolder({
			'./services/one/workflow_manifest.json': { id: 'one' },
			'./services/one/start.json': { process_id: 'start' },
			'./services/two/workflow_manifest.json': { id: 'two' }
		});

		expect(Object.keys(grouped)).toEqual(['one', 'two']);
		expect(Object.keys(grouped.one)).toEqual(['workflow_manifest.json', 'start.json']);
	});
});

describe('loadExamples', () => {
	it('keeps an example that fails the schema in the list, with its problems and no workflow', () => {
		const [broken] = loadExamples({ broken: { 'workflow_manifest.json': {} } });

		expect(broken.slug).toBe('broken');
		expect(broken.workflow).toBeNull();
		expect(broken.issues.length).toBeGreaterThan(0);
		expect(broken.warnings).toEqual([]);
	});

	it('lists the examples in name order', () => {
		const slugs = loadExamples({ b: {}, a: {}, c: {} }).map((example) => example.slug);
		expect(slugs).toEqual(['a', 'b', 'c']);
	});
});
