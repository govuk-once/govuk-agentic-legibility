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
		expect(stateSchema.safeParse({ type: 'end', status: 'success' }).success).toBe(true);
		expect(stateSchema.safeParse({ type: 'wait', duration: 'PT5S', next: 'a' }).success).toBe(true);
		expect(stateSchema.safeParse({ type: 'output', channel: 'transcript', message: 'Hello', next: 'a' }).success).toBe(true);
	});

	it('applies the rules of the matching state only', () => {
		// A wait state may not have a status, which only an end state uses.
		expect(stateSchema.safeParse({ type: 'wait', duration: 'PT5S', next: 'a', status: 'success' }).success).toBe(false);
		// An output rule still applies when the output sits inside the union.
		expect(stateSchema.safeParse({ type: 'output', channel: 'transcript', next: 'a' }).success).toBe(false);
	});

	it('rejects an unknown type and a state with no type', () => {
		expect(stateSchema.safeParse({ type: 'decide', rules: [], default: 'a' }).success).toBe(false);
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
				type: 'input',
				prompt: 'Did you attend?',
				schema: { kind: 'boolean' },
				assign: 'attended',
				next: 'finish'
			},
			finish: { type: 'end', status: 'success' }
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
		const broken = { ...process, states: { ...process.states, finish: { type: 'end' } } };
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
