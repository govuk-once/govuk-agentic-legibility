import { describe, expect, it } from 'vitest';
import type { Manifest, Workflow } from '$lib/schema/workflow/workflow';
import { withTechReviewChecked } from '../step-values/step-values';
import { describeWorkflowSettings, isTechReviewFinished } from '../tech-review-summary';

describe('describeWorkflowSettings', () => {
	it('writes the run timeout and the API call defaults in words', () => {
		const manifest = {
			executor: { run_timeout: 'P7D' },
			defaults: { api_call: { timeouts: { start_to_close: 'PT30S' }, retry: { max_attempts: 3, initial_interval: 'PT5S' } } }
		} as unknown as Manifest;
		expect(describeWorkflowSettings(manifest)).toEqual({
			runTimeout: '7 days',
			apiCalls: 'time limit 30 seconds, tried 3 times, 5 seconds between tries'
		});
	});
});

describe('isTechReviewFinished', () => {
	// A journey with one connected call and one wait.
	const workflow = {
		manifest: { entry: 'demo' },
		processes: {
			demo: {
				process_id: 'demo',
				version: '0.1.0',
				start: 'send',
				states: {
					send: { state_type: 'api_call', method: 'POST', service: 'govuk_forms', url: '/send', next: 'pause' },
					pause: { state_type: 'wait', duration: 'PT30M', next: 'done' },
					done: { state_type: 'end', status: 'success' }
				}
			}
		}
	} as unknown as Workflow;

	it('is finished once a sent review has checked every developer step', () => {
		expect(isTechReviewFinished(workflow)).toBe(false);
		expect(isTechReviewFinished(withTechReviewChecked(workflow, 'now'))).toBe(true);
	});

	it('is not finished while an API call is unconnected', () => {
		const unconnected = { ...workflow.processes.demo.states.send, service: 'unconnected_service' };
		const process = { ...workflow.processes.demo, states: { ...workflow.processes.demo.states, send: unconnected } };
		const withUnconnected = { ...workflow, processes: { demo: process } } as unknown as Workflow;
		expect(isTechReviewFinished(withTechReviewChecked(withUnconnected, 'now'))).toBe(false);
	});
});
