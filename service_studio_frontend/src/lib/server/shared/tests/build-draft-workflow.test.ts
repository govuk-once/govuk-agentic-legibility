import { describe, expect, it } from 'vitest';
import type { Process } from '$lib/schema/workflow/process';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import { buildDraftWorkflow } from '../build-draft-workflow';

const details = { name: 'Tell us about a change', description: 'Report a change.', links: ['https://www.gov.uk/a', 'https://example.com/b'] };
const settings = { defaults: {}, runTimeout: 'P3D' };

// A journey of one question and an end, as the model might write it. The cast is needed because it gives only the keys it uses.
const generated = {
	process_id: 'main',
	version: '9.9.9',
	start: 'ask',
	vars: {},
	states: {
		ask: { state_type: 'input', prompt: 'What changed?', schema: { kind: 'string' }, assign: 'change', next: 'finish' },
		finish: { state_type: 'end', status: 'success' }
	}
} as unknown as Process;

describe('buildDraftWorkflow', () => {
	it('gives a workflow that passes the schema checks', () => {
		const result = parseWorkflow(buildDraftWorkflow(generated, details, settings));
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});

	it('names the workflow and its one process after what the person called it', () => {
		const { manifest, processes } = buildDraftWorkflow(generated, details, settings);
		expect(manifest).toMatchObject({
			id: 'draft.tell_us_about_a_change',
			entry: 'tell_us_about_a_change',
			description: 'Report a change.',
			state: 'draft',
			processes: [{ process_id: 'tell_us_about_a_change', version: '0.1.0' }]
		});
		expect(processes.tell_us_about_a_change).toMatchObject({ process_id: 'tell_us_about_a_change', version: '0.1.0' });
	});

	it('gives the owner and the contact placeholders, to be replaced at a later review', () => {
		const { manifest } = buildDraftWorkflow(generated, details, settings);
		expect(manifest.owner).toBe('To be confirmed');
		expect(manifest.contact).toBe('to.be.confirmed@example.com');
	});

	it('uses the defaults and the run limit of the kind of draft', () => {
		const { manifest } = buildDraftWorkflow(generated, details, settings);
		expect(manifest.defaults).toEqual({});
		expect(manifest.executor.run_timeout).toBe('P3D');
	});

	it('keeps only the links the assistant may read as the sources of the process', () => {
		const { manifest, processes } = buildDraftWorkflow(generated, details, settings);
		expect(processes[manifest.entry].source).toEqual(['https://www.gov.uk/a']);
	});

	it('does not change the process it was given', () => {
		const before = JSON.stringify(generated);
		buildDraftWorkflow(generated, details, settings);
		expect(JSON.stringify(generated)).toBe(before);
	});
});
