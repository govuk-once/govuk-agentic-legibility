import { describe, expect, it } from 'vitest';
import { exampleProcessFiles } from './example-states';
import { processSchema, stateSchema } from '../process';

describe('processSchema with the real examples', () => {
	it('accepts every process file in the example services', () => {
		const files = exampleProcessFiles();
		expect(files.length).toBe(14);
		for (const file of files) {
			const result = processSchema.safeParse(file);
			expect(result.success, JSON.stringify(result.error?.issues.slice(0, 3))).toBe(true);
		}
	});
});

describe('stateSchema', () => {
	it('picks the right schema from the type', () => {
		expect(stateSchema.safeParse({ state_type: 'end', status: 'success' }).success).toBe(true);
		expect(stateSchema.safeParse({ state_type: 'wait', duration: 'PT5S', next: 'a' }).success).toBe(true);
		expect(stateSchema.safeParse({ state_type: 'output', channel: 'transcript', message: 'Hello', next: 'a' }).success).toBe(true);
	});

	it('applies the rules of the matching state only', () => {
		// A wait state may not have a status, which only an end state uses.
		expect(stateSchema.safeParse({ state_type: 'wait', duration: 'PT5S', next: 'a', status: 'success' }).success).toBe(false);
		// An output rule still applies when the output sits inside the union.
		expect(stateSchema.safeParse({ state_type: 'output', channel: 'transcript', next: 'a' }).success).toBe(false);
	});

	it('rejects an unknown type and a state with no type', () => {
		expect(stateSchema.safeParse({ state_type: 'decide', rules: [], default: 'a' }).success).toBe(false);
		expect(stateSchema.safeParse({ next: 'a' }).success).toBe(false);
	});
});

describe('processSchema', () => {
	const process = {
		process_id: 'check_attendance',
		version: '0.1.0',
		start: 'ask',
		vars: { attended: null },
		states: {
			ask: {
				state_type: 'input',
				prompt: 'Did you attend?',
				schema: { kind: 'boolean' },
				assign: 'attended',
				next: 'finish'
			},
			finish: { state_type: 'end', status: 'success' }
		}
	};

	it('accepts a small process', () => {
		expect(processSchema.safeParse(process).success).toBe(true);
	});

	it('accepts notes, a performer, source links and an opening window', () => {
		const detailed = {
			...process,
			metadata: { title: 'Check attendance' },
			performer: 'dwp',
			source: ['https://www.gov.uk/maternity-allowance'],
			window: { start: '2026-01-01', end: '2026-12-31' }
		};
		expect(processSchema.safeParse(detailed).success).toBe(true);
		expect(processSchema.safeParse({ ...process, window: null }).success).toBe(true);
	});

	it.each(['process_id', 'version', 'start', 'vars', 'states'])('rejects a process with no %s', (key) => {
		const { [key as keyof typeof process]: _removed, ...incomplete } = process;
		expect(processSchema.safeParse(incomplete).success).toBe(false);
	});

	it('rejects a process with no states', () => {
		expect(processSchema.safeParse({ ...process, states: {} }).success).toBe(false);
	});

	it('rejects an invalid state inside the process', () => {
		const broken = { ...process, states: { ...process.states, finish: { state_type: 'end' } } };
		expect(processSchema.safeParse(broken).success).toBe(false);
	});

	it('rejects a version that is not three numbers', () => {
		expect(processSchema.safeParse({ ...process, version: '1' }).success).toBe(false);
	});

	it('rejects a variable name that is not a valid path', () => {
		expect(processSchema.safeParse({ ...process, vars: { 'not a path': 1 } }).success).toBe(false);
	});

	it('rejects a source that is not a web address and a window with a bad date', () => {
		expect(processSchema.safeParse({ ...process, source: ['gov.uk'] }).success).toBe(false);
		expect(processSchema.safeParse({ ...process, window: { start: 'soon', end: '2026-12-31' } }).success).toBe(false);
	});

	it('rejects parent_process, which the invoke state makes unnecessary', () => {
		expect(processSchema.safeParse({ ...process, parent_process: null }).success).toBe(false);
	});
});

describe('the type alias for state_type', () => {
	const wait = { duration: 'PT5S', next: 'a' };

	it('accepts the key type, as the executor and the form files write it, and gives it back as state_type', () => {
		const result = stateSchema.safeParse({ type: 'wait', ...wait });
		expect(result.success).toBe(true);
		expect(result.data).toEqual({ state_type: 'wait', ...wait });
	});

	it('accepts the key state_type as it is', () => {
		const result = stateSchema.safeParse({ state_type: 'wait', ...wait });
		expect(result.data).toEqual({ state_type: 'wait', ...wait });
	});

	it('refuses a state that has both keys, and says the key that is extra', () => {
		const result = stateSchema.safeParse({ type: 'wait', state_type: 'wait', ...wait });
		expect(result.success).toBe(false);
		expect(result.error?.issues[0].message).toContain('type');
	});

	it('refuses a state that has neither key', () => {
		expect(stateSchema.safeParse(wait).success).toBe(false);
	});

	it('still flags a misspelt key on a state that uses the alias', () => {
		expect(stateSchema.safeParse({ type: 'wait', ...wait, nxt: 'b' }).success).toBe(false);
	});

	it('does not change anything that is not an object', () => {
		for (const value of [null, 'wait', 3, ['wait']]) expect(stateSchema.safeParse(value).success).toBe(false);
	});

	it('loads every process file of the example services written with the key type, with state_type coming out', () => {
		for (const file of exampleProcessFiles() as { states: Record<string, Record<string, unknown>> }[]) {
			const withAlias = {
				...file,
				states: Object.fromEntries(
					Object.entries(file.states).map(([code, state]) => {
						const { state_type, ...rest } = state;
						return [code, { type: state_type, ...rest }];
					})
				)
			};
			const result = processSchema.safeParse(withAlias);
			expect(result.success, JSON.stringify(result.error?.issues.slice(0, 3))).toBe(true);
			for (const state of Object.values(result.data?.states ?? {})) expect(state).toHaveProperty('state_type');
			for (const state of Object.values(result.data?.states ?? {})) expect(state).not.toHaveProperty('type');
		}
	});
});
