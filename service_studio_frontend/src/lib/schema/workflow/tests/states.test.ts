import { describe, expect, it } from 'vitest';
import { exampleStatesOfType } from './example-states';
import { assignStateSchema, endStateSchema, outputStateSchema, waitStateSchema } from '../states';

describe('simple states with the real examples', () => {
	const schemas = {
		output: outputStateSchema,
		assign: assignStateSchema,
		wait: waitStateSchema,
		end: endStateSchema
	};

	for (const [type, schema] of Object.entries(schemas)) {
		it(`accepts every ${type} state in the example files`, () => {
			const states = exampleStatesOfType(type);
			expect(states.length).toBeGreaterThan(0);
			for (const state of states) {
				const result = schema.safeParse(state);
				expect(result.success, JSON.stringify(state)).toBe(true);
			}
		});
	}
});

describe('baseStateFields', () => {
	it('accepts a title and notes on a state', () => {
		const state = { type: 'wait', name: 'Wait for the post', metadata: { description: 'Gives time.' }, duration: 'P2D', next: 'check' };
		expect(waitStateSchema.safeParse(state).success).toBe(true);
	});

	it('rejects an empty title and notes that hold nested data', () => {
		const base = { type: 'wait', duration: 'P2D', next: 'check' };
		expect(waitStateSchema.safeParse({ ...base, name: '' }).success).toBe(false);
		expect(waitStateSchema.safeParse({ ...base, metadata: { count: { a: 2 } } }).success).toBe(false);
	});

	it('accepts notes that hold a number, true or false, or null', () => {
		const base = { type: 'wait', duration: 'P2D', next: 'check' };
		expect(waitStateSchema.safeParse({ ...base, metadata: { count: 2, checked: true, hint: null } }).success).toBe(true);
	});

	it('rejects a key the document does not list', () => {
		const state = { type: 'wait', duration: 'P2D', next: 'check', timeout: 'P1D' };
		expect(waitStateSchema.safeParse(state).success).toBe(false);
	});
});

describe('outputStateSchema', () => {
	it('accepts a transcript message', () => {
		const state = { type: 'output', channel: 'transcript', message: 'Thank you {{name}}.', next: 'ask' };
		expect(outputStateSchema.safeParse(state).success).toBe(true);
	});

	it('accepts an email built from a template and references', () => {
		const state = {
			type: 'output',
			channel: 'email',
			template: 'application_submitted',
			params: { email: { $: 'input.email' } },
			idempotency_key: '{{workflow_id}}:email',
			also_transcript: 'We have emailed you.',
			on_error: 'continue',
			next: 'done'
		};
		expect(outputStateSchema.safeParse(state).success).toBe(true);
	});

	it('rejects a transcript output with no message', () => {
		const state = { type: 'output', channel: 'transcript', next: 'ask' };
		expect(outputStateSchema.safeParse(state).success).toBe(false);
	});

	it.each(['email', 'sms'])('rejects a %s output with no template', (channel) => {
		const state = { type: 'output', channel, message: 'Hello', next: 'ask' };
		expect(outputStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects an unknown channel and a missing next state', () => {
		expect(outputStateSchema.safeParse({ type: 'output', channel: 'post', message: 'x', next: 'a' }).success).toBe(false);
		expect(outputStateSchema.safeParse({ type: 'output', channel: 'transcript', message: 'x' }).success).toBe(false);
	});

	it('rejects an unknown on_error value', () => {
		const state = { type: 'output', channel: 'transcript', message: 'x', on_error: 'retry', next: 'a' };
		expect(outputStateSchema.safeParse(state).success).toBe(false);
	});
});

describe('assignStateSchema', () => {
	it('accepts a counter, a reference and a literal', () => {
		const state = {
			type: 'assign',
			set: {
				upload_attempts: { op: 'add', path: 'upload_attempts', value: 1 },
				driver_id: { $: 'driver_info.driver_id' },
				confirmed: true
			},
			next: 'prompt'
		};
		expect(assignStateSchema.safeParse(state).success).toBe(true);
	});

	it('rejects a variable name that is not a valid path', () => {
		const state = { type: 'assign', set: { 'not a path': 1 }, next: 'prompt' };
		expect(assignStateSchema.safeParse(state).success).toBe(false);
	});

	it('rejects an invalid expression and a missing set', () => {
		expect(assignStateSchema.safeParse({ type: 'assign', set: { a: { op: 'multiply' } }, next: 'x' }).success).toBe(false);
		expect(assignStateSchema.safeParse({ type: 'assign', next: 'x' }).success).toBe(false);
	});
});

describe('waitStateSchema', () => {
	it('accepts a written duration and a reference to one', () => {
		expect(waitStateSchema.safeParse({ type: 'wait', duration: 'P7D', next: 'ask' }).success).toBe(true);
		expect(waitStateSchema.safeParse({ type: 'wait', duration: { $: 'poll_interval' }, next: 'ask' }).success).toBe(true);
	});

	it('rejects a duration written as plain words and a missing next state', () => {
		expect(waitStateSchema.safeParse({ type: 'wait', duration: 'a week', next: 'ask' }).success).toBe(false);
		expect(waitStateSchema.safeParse({ type: 'wait', duration: 'P7D' }).success).toBe(false);
	});
});

describe('endStateSchema', () => {
	it.each(['success', 'cancelled', 'failed', 'offramp', 'needs_attention'])('accepts the status %s', (status) => {
		expect(endStateSchema.safeParse({ type: 'end', status }).success).toBe(true);
	});

	it('accepts an outcome and a returned value', () => {
		const state = { type: 'end', status: 'success', outcome: 'claim_submitted_online', return: { photo_id: { $: 'photo.id' } } };
		expect(endStateSchema.safeParse(state).success).toBe(true);
	});

	it('accepts a return value of null', () => {
		expect(endStateSchema.safeParse({ type: 'end', status: 'cancelled', return: null }).success).toBe(true);
	});

	it('rejects a missing or unknown status', () => {
		expect(endStateSchema.safeParse({ type: 'end' }).success).toBe(false);
		expect(endStateSchema.safeParse({ type: 'end', status: 'done' }).success).toBe(false);
	});

	it('rejects a next state, because an end state has no way on', () => {
		expect(endStateSchema.safeParse({ type: 'end', status: 'success', next: 'x' }).success).toBe(false);
	});
});
