import { describe, expect, it } from 'vitest';
import {
	callStateSchema,
	captureSpecSchema,
	catchClauseSchema,
	retryPolicySchema,
	timeoutsSchema
} from '../call-state';
import { exampleStatesOfType } from './example-states';

type ExampleManifest = { defaults?: { call?: { timeouts?: unknown; retry?: unknown } } };

// The workflow manifest of each example service, which holds the default timeouts and retry policy.
const manifests = Object.values(
	import.meta.glob('../../../examples/services/*/workflow_manifest.json', {
		eager: true,
		import: 'default'
	})
) as ExampleManifest[];

describe('callStateSchema with the real examples', () => {
	it('accepts every call state in the example files', () => {
		const states = exampleStatesOfType('call');
		expect(states.length).toBeGreaterThan(10);
		for (const state of states) {
			const result = callStateSchema.safeParse(state);
			expect(result.success, JSON.stringify(state)).toBe(true);
		}
	});

	it('accepts the default timeouts and retry policy in every manifest', () => {
		expect(manifests.length).toBeGreaterThan(0);
		for (const manifest of manifests) {
			expect(timeoutsSchema.safeParse(manifest.defaults?.call?.timeouts).success).toBe(true);
			expect(retryPolicySchema.safeParse(manifest.defaults?.call?.retry).success).toBe(true);
		}
	});
});

describe('callStateSchema', () => {
	const call = { type: 'call', method: 'GET', service: 'dvla', url: '/drivers/{{driver_id}}', next: 'show_driver' };

	it('accepts a minimal call', () => {
		expect(callStateSchema.safeParse(call).success).toBe(true);
	});

	it('accepts a call with every optional key', () => {
		const state = {
			...call,
			method: 'POST',
			name: 'Upload the photo',
			metadata: { description: 'Sends the photo to the licence service.' },
			headers: { 'X-Request-Source': 'service-studio' },
			body: { driver_id: { $: 'input.driver_id' }, attempt: { op: 'add', path: 'attempts', value: 1 } },
			source_ref: { $: 'photo_file.ref' },
			encoding: 'multipart',
			idempotency_key: '{{workflow_id}}:upload_photo',
			timeouts: { start_to_close: 'PT30S' },
			retry: { max_attempts: 3, retry_on: ['5xx', 'timeout'] },
			assign: 'upload_res',
			capture: { photo_id: 'body.photo_id', names: { from: 'body.names', pick: ['first'], max_items: 5 } },
			catch: [{ on: 'any', next: 'upload_failed' }]
		};
		expect(callStateSchema.safeParse(state).success).toBe(true);
	});

	it.each(['method', 'service', 'url', 'next'])('rejects a call with no %s', (key) => {
		const { [key as keyof typeof call]: _removed, ...state } = call;
		expect(callStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects an unknown method', () => {
		expect(callStateSchema.safeParse({ ...call, method: 'FETCH' }).success).toBe(false);
	});

	it('rejects a body value that is not a valid expression', () => {
		const state = { ...call, body: { a: { op: 'multiply', path: 'x', value: 2 } } };
		expect(callStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects a capture name that is not a valid path', () => {
		expect(callStateSchema.safeParse({ ...call, capture: { 'not a path': 'body.x' } }).success).toBe(false);
	});
});

describe('timeoutsSchema', () => {
	it('accepts any mix of the three limits', () => {
		expect(timeoutsSchema.safeParse({}).success).toBe(true);
		expect(timeoutsSchema.safeParse({ start_to_close: 'PT15S', heartbeat: 'PT5S' }).success).toBe(true);
	});

	it('rejects a limit that is not a duration and a limit the document does not list', () => {
		expect(timeoutsSchema.safeParse({ start_to_close: '15 seconds' }).success).toBe(false);
		expect(timeoutsSchema.safeParse({ total: 'PT15S' }).success).toBe(false);
	});
});

describe('retryPolicySchema', () => {
	it('accepts a full policy', () => {
		const policy = {
			max_attempts: 3,
			initial_interval: 'PT1S',
			backoff_coefficient: 2.0,
			max_interval: 'PT30S',
			retry_on: ['5xx', '429', 'timeout', 'connection']
		};
		expect(retryPolicySchema.safeParse(policy).success).toBe(true);
	});

	it('rejects zero attempts, an empty retry_on list and an unknown failure kind', () => {
		expect(retryPolicySchema.safeParse({ max_attempts: 0 }).success).toBe(false);
		expect(retryPolicySchema.safeParse({ retry_on: [] }).success).toBe(false);
		expect(retryPolicySchema.safeParse({ retry_on: ['404'] }).success).toBe(false);
	});
});

describe('catchClauseSchema', () => {
	it('accepts a named error and the any catch all', () => {
		expect(catchClauseSchema.safeParse({ on: 'api_failure', next: 'end_exception' }).success).toBe(true);
		expect(catchClauseSchema.safeParse({ on: 'any', next: 'retry' }).success).toBe(true);
	});

	it('rejects a clause with no error name or no next state', () => {
		expect(catchClauseSchema.safeParse({ next: 'x' }).success).toBe(false);
		expect(catchClauseSchema.safeParse({ on: 'any' }).success).toBe(false);
	});
});

describe('captureSpecSchema', () => {
	it('accepts a path as plain text or the longer form', () => {
		expect(captureSpecSchema.safeParse('body.photo_id').success).toBe(true);
		expect(captureSpecSchema.safeParse({ from: 'body.items', max_length: 200 }).success).toBe(true);
	});

	it('rejects an empty path and a longer form with no from', () => {
		expect(captureSpecSchema.safeParse('').success).toBe(false);
		expect(captureSpecSchema.safeParse({ pick: ['a'] }).success).toBe(false);
	});
});
