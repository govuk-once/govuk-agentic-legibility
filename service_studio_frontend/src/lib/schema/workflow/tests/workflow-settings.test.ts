import { describe, expect, it } from 'vitest';
import { placeholderApiCallDefaults } from '../placeholders';
import type { Manifest } from '../workflow';
import type { WorkingProcess } from '../working-process';
import {
	longestWait,
	withWorkflowSettings,
	workflowSettingsOf,
	workflowSettingsProblems,
	type WorkflowSettings
} from '../workflow-settings';

// Only the keys the settings read and write. The cast is needed because a test gives only the keys it uses.
const manifestWith = (keys: Partial<Manifest>) =>
	({ executor: { run_timeout: 'P7D', workflow_id_template: 't', id_reuse_policy: 'reject_duplicate', search_attributes: {} }, defaults: {}, ...keys }) as Manifest;

const filledIn: WorkflowSettings = { runTimeout: '7', runTimeoutUnit: 'days', callTimeout: '30', attempts: '3', pauseBetween: '5' };

describe('workflowSettingsOf', () => {
	it('reads the run timeout and shows the placeholder call defaults when none are set', () => {
		expect(workflowSettingsOf(manifestWith({}))).toEqual({
			runTimeout: '7',
			runTimeoutUnit: 'days',
			callTimeout: '15',
			attempts: '3',
			pauseBetween: '1'
		});
	});

	it('reads the call defaults the manifest sets', () => {
		const manifest = manifestWith({
			defaults: { api_call: { timeouts: { start_to_close: 'PT30S' }, retry: { max_attempts: 5, initial_interval: 'PT10S' } } }
		});
		expect(workflowSettingsOf(manifest)).toMatchObject({ callTimeout: '30', attempts: '5', pauseBetween: '10' });
	});
});

describe('withWorkflowSettings', () => {
	it('writes the run timeout and the call defaults, keeping the rest of the retry policy', () => {
		const manifest = withWorkflowSettings(manifestWith({}), { ...filledIn, runTimeout: '12', runTimeoutUnit: 'hours' });
		expect(manifest.executor.run_timeout).toBe('PT12H');
		expect(manifest.executor.workflow_id_template).toBe('t');
		expect(manifest.defaults.api_call).toEqual({
			timeouts: { start_to_close: 'PT30S' },
			retry: { ...placeholderApiCallDefaults.retry, max_attempts: 3, initial_interval: 'PT5S' }
		});
	});

	it('reads back what it wrote', () => {
		expect(workflowSettingsOf(withWorkflowSettings(manifestWith({}), filledIn))).toEqual(filledIn);
	});
});

describe('workflowSettingsProblems', () => {
	it('has nothing to say about whole numbers', () => {
		expect(workflowSettingsProblems(filledIn)).toEqual([]);
	});

	it('asks for whole numbers in the order the fields are shown', () => {
		const typed = { ...filledIn, runTimeout: '', callTimeout: '0', attempts: '2.5', pauseBetween: 'soon' };
		expect(workflowSettingsProblems(typed).map((problem) => problem.field)).toEqual(['runTimeout', 'callTimeout', 'attempts', 'pauseBetween']);
	});

	it('allows no pause between tries', () => {
		expect(workflowSettingsProblems({ ...filledIn, pauseBetween: '0' })).toEqual([]);
	});
});

describe('longestWait', () => {
	it('finds the longest wait written in the file, and leaves out one held in a variable', () => {
		const process = {
			states: {
				short: { state_type: 'wait', duration: 'PT5M', next: 'long' },
				long: { state_type: 'wait', duration: 'PT30M', next: 'held' },
				held: { state_type: 'wait', duration: { $: 'poll_interval' }, next: 'done' },
				done: { state_type: 'end', status: 'success' }
			}
		} as unknown as WorkingProcess;
		expect(longestWait(process)).toEqual({ code: 'long', seconds: 1800 });
	});

	it('finds nothing in a process with no waits', () => {
		expect(longestWait({ states: {} } as unknown as WorkingProcess)).toBeUndefined();
	});
});
