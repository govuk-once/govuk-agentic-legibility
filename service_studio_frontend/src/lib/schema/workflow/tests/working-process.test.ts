import { describe, expect, it } from 'vitest';
import { processSchema, type Process } from '../process';
import type { WorkingProcess } from '../working-process';

// A process with a step that is not joined to anything. The cast is needed because it does not match the saved shape.
const unfinished = {
	process_id: 'p',
	version: '0.1.0',
	vars: {},
	start: 'a',
	states: { a: { state_type: 'wait', duration: 'PT1S' } }
} as unknown as WorkingProcess;

describe('WorkingProcess', () => {
	it('accepts a saved process wherever an editing one is expected', () => {
		const saved: Process = {
			process_id: 'p',
			version: '0.1.0',
			vars: {},
			start: 'a',
			states: { a: { state_type: 'wait', duration: 'PT1S', next: 'end' }, end: { state_type: 'end', status: 'success' } }
		};
		const editing: WorkingProcess = saved;
		expect(editing.start).toBe('a');
	});

	it('is still refused by the saved shape, so a missing next is reported when the journey is checked', () => {
		expect(processSchema.safeParse(unfinished).success).toBe(false);
	});
});
