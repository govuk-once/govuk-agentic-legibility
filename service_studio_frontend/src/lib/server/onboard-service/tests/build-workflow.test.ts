import { describe, expect, it } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import { placeholderApiCallDefaults, placeholderRunTimeout } from '$lib/schema/workflow/placeholders';
import type { Process } from '$lib/schema/workflow/process';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import { buildWorkflow, withFailureRoutes } from '../build-workflow';

const details = { name: 'Change driving licence address', description: 'Change an address.', links: ['https://www.gov.uk/change-address'] };

// A small journey of a question, an API call and an end, as the model might produce it. The cast is needed because
// each test gives only the keys it uses.
const generated = (states: Record<string, unknown> = {}) =>
	({
		process_id: 'whatever',
		version: '9.9.9',
		start: 'ask',
		vars: {},
		states: {
			ask: { type: 'input', prompt: 'Postcode?', schema: { kind: 'string' }, assign: 'postcode', next: 'look_up' },
			look_up: { type: 'api_call', method: 'GET', service: 'unconnected_service', url: '/unconnected', next: 'finish' },
			finish: { type: 'end', status: 'success' },
			...states
		}
	}) as unknown as Process;

describe('withFailureRoutes', () => {
	it('adds one failed end and sends every call without an error route to it', () => {
		const process = generated({ send: { type: 'api_call', method: 'POST', service: 's', url: '/u', next: 'finish' } });
		const result = withFailureRoutes(process);

		expect(result.states.end_failed).toMatchObject({ type: 'end', status: 'failed' });
		expect(result.states.look_up).toMatchObject({ catch: [{ on: 'any', next: 'end_failed' }] });
		expect(result.states.send).toMatchObject({ catch: [{ on: 'any', next: 'end_failed' }] });
	});

	it('leaves a call that already says where its errors go', () => {
		const own = { type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'finish', catch: [{ on: 'api_failure', next: 'finish' }] };
		const result = withFailureRoutes(generated({ look_up: own }));
		expect(result.states.look_up).toEqual(own);
		expect(result.states.end_failed).toBeUndefined();
	});

	it('adds nothing when there is no call', () => {
		const process = generated();
		const { look_up: _gone, ...states } = process.states;
		const noCalls = { ...process, states: { ...states, ask: { ...process.states.ask, next: 'finish' } } } as Process;
		expect(withFailureRoutes(noCalls)).toBe(noCalls);
	});

	it('gives the end a name that no state already has', () => {
		const result = withFailureRoutes(generated({ end_failed: { type: 'end', status: 'cancelled' } }));
		expect(result.states.end_failed).toMatchObject({ status: 'cancelled' });
		expect(result.states.end_failed_2).toMatchObject({ status: 'failed' });
		expect(result.states.look_up).toMatchObject({ catch: [{ next: 'end_failed_2' }] });
	});

	it('does not change the process it was given', () => {
		const process = generated();
		const before = JSON.stringify(process);
		withFailureRoutes(process);
		expect(JSON.stringify(process)).toBe(before);
	});
});

describe('buildWorkflow', () => {
	it('gives a workflow that passes the schema checks', () => {
		const result = parseWorkflow(buildWorkflow(generated(), details));
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});

	it('fills the manifest with placeholders and the details the person typed', () => {
		const { manifest } = buildWorkflow(generated(), details);
		expect(manifest).toMatchObject({
			schema: 'Workflow/0.2',
			id: 'draft.change_driving_licence_address',
			state: 'draft',
			owner: 'To be confirmed',
			description: 'Change an address.',
			entry: 'change_driving_licence_address',
			processes: [{ process_id: 'change_driving_licence_address', version: '0.1.0' }]
		});
	});

	it('uses the same run limit and call defaults as the real example services', () => {
		const example = serviceExamples.find((candidate) => candidate.slug === 'change_of_address')?.workflow;
		const { manifest } = buildWorkflow(generated(), details);
		expect(manifest.defaults).toEqual({ api_call: placeholderApiCallDefaults });
		expect(manifest.defaults).toEqual(example?.manifest.defaults);
		expect(manifest.executor.run_timeout).toBe(placeholderRunTimeout);
		expect(manifest.executor.run_timeout).toBe(example?.manifest.executor.run_timeout);
	});

	it('gives the process the id and version the manifest lists, whatever the model wrote', () => {
		const { manifest, processes } = buildWorkflow(generated(), details);
		const process = processes[manifest.entry];
		expect(process).toMatchObject({ process_id: manifest.entry, version: '0.1.0' });
	});

	it('uses the links the person gave as sources and leaves out one that is not a web address', () => {
		const { manifest, processes } = buildWorkflow(generated(), { ...details, links: ['https://a.gov.uk/x', 'not a link', ''] });
		expect(processes[manifest.entry].source).toEqual(['https://a.gov.uk/x']);
	});

	it('leaves out a link that does not use http or https, such as an email link or a file', () => {
		const links = ['http://b.gov.uk/y', 'mailto:team@example.gov.uk', 'file:///etc/passwd'];
		const { manifest, processes } = buildWorkflow(generated(), { ...details, links });
		expect(processes[manifest.entry].source).toEqual(['http://b.gov.uk/y']);
	});

	it('keeps the sources the process already had when no usable link was given', () => {
		const process = { ...generated(), source: ['https://b.gov.uk/y'] } as Process;
		const { manifest, processes } = buildWorkflow(process, { ...details, links: ['', 'nonsense'] });
		expect(processes[manifest.entry].source).toEqual(['https://b.gov.uk/y']);
	});

	it('adds the failed end and the call error route', () => {
		const { manifest, processes } = buildWorkflow(generated(), details);
		expect(processes[manifest.entry].states.look_up).toMatchObject({ catch: [{ on: 'any' }] });
	});

	it('does not change the process it was given', () => {
		const process = generated();
		const before = JSON.stringify(process);
		buildWorkflow(process, details);
		expect(JSON.stringify(process)).toBe(before);
	});
});
