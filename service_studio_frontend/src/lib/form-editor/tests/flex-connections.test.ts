import { describe, expect, it } from 'vitest';
import type { Workflow } from '$lib/schema/workflow/workflow';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { placeholderBodyValue } from '$lib/schema/workflow/placeholders';
import { apiCallSteps, bodyForEndpoint, flexConnections, summariseBody, usesEndpoint, withEndpoint, type FlexEndpoint } from '$lib/form-editor/flex-connections';

// A short journey with a connected call, a question and an unconnected call, drawn in that order.
const process = {
	process_id: 'demo',
	version: '0.1.0',
	start: 'lookup',
	states: {
		lookup: { state_type: 'api_call', name: 'Look up licence', method: 'GET', service: 'dvla', url: '/licences', next: 'ask' },
		ask: { state_type: 'input', prompt: 'What is your name?', schema: { kind: 'string' }, assign: 'name', next: 'send' },
		send: {
			state_type: 'api_call',
			name: 'Send form',
			method: 'GET',
			service: 'unconnected_service',
			url: '/unconnected',
			body: { name: { $: 'name' } },
			next: 'done'
		},
		done: { state_type: 'end', status: 'success' }
	}
} as unknown as WorkingProcess;

const workflow = { manifest: { entry: 'demo' }, processes: { demo: process } } as unknown as Workflow;

const endpoint: FlexEndpoint = {
	method: 'POST',
	service: 'govuk_forms',
	url: '/app/forms/v1/submissions',
	description: 'Send a completed form',
	bodyFields: ['name', 'declaration']
};

const readOnlyEndpoint: FlexEndpoint = { method: 'GET', service: 'govuk_forms', url: '/app/forms/v1/status', description: 'Check a form' };

describe('apiCallSteps', () => {
	it('lists the API calls in journey order and says which are connected', () => {
		expect(apiCallSteps(process)).toEqual([
			{ code: 'lookup', title: 'Look up licence', stateType: 'api_call', method: 'GET', url: '/licences', connected: true },
			{ code: 'send', title: 'Send form', stateType: 'api_call', method: 'GET', url: '/unconnected', connected: false }
		]);
	});
});

describe('flexConnections', () => {
	it('counts the API calls and how many are connected', () => {
		expect(flexConnections(process)).toEqual({ connected: 1, total: 2 });
	});
});

describe('withEndpoint', () => {
	it('writes the endpoint into the call and keeps the rest of the step', () => {
		const send = withEndpoint(workflow, 'send', endpoint).processes.demo.states.send;
		expect(send).toMatchObject({
			method: 'POST',
			service: 'govuk_forms',
			url: '/app/forms/v1/submissions',
			body: { name: { $: 'name' }, declaration: placeholderBodyValue },
			next: 'done'
		});
	});

	it('saves the call without a body when the endpoint takes none', () => {
		const send = withEndpoint(workflow, 'send', readOnlyEndpoint).processes.demo.states.send;
		expect(send).not.toHaveProperty('body');
	});

	it('leaves the form as it is for a step that is not an API call', () => {
		expect(withEndpoint(workflow, 'ask', endpoint)).toBe(workflow);
	});
});

describe('usesEndpoint', () => {
	it('matches a call that holds the same method, service and url', () => {
		expect(usesEndpoint({ method: 'POST', service: 'govuk_forms', url: '/app/forms/v1/submissions' }, endpoint)).toBe(true);
		expect(usesEndpoint({ method: 'GET', service: 'govuk_forms', url: '/app/forms/v1/submissions' }, endpoint)).toBe(false);
	});
});

describe('bodyForEndpoint', () => {
	it('keeps the fields the endpoint expects, adds the missing ones as placeholders and leaves out the rest', () => {
		expect(bodyForEndpoint({ name: { $: 'name' }, old_field: 'x' }, endpoint)).toEqual({ name: { $: 'name' }, declaration: placeholderBodyValue });
	});

	it('gives no body for an endpoint that takes none', () => {
		expect(bodyForEndpoint({ name: { $: 'name' } }, readOnlyEndpoint)).toBeUndefined();
	});
});


describe('summariseBody', () => {
	it('counts the fields and how many still need a value', () => {
		expect(summariseBody({ name: { $: 'name' }, declaration: placeholderBodyValue })).toEqual({ fields: 2, toFillIn: 1 });
	});
});
