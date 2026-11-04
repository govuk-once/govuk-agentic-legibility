import { describe, expect, it } from 'vitest';
import { workflowExamples } from '$lib/examples/workflows';
import type { Process } from '$lib/schema/workflow/process';
import { processToGraph, stepCount } from '../process-to-graph';
import { stateRows } from '../state-rows';

const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

describe('stateRows', () => {
	const process = build('ask', {
		ask: { type: 'input', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'check' },
		check: { type: 'choice', name: 'Is it right?', rules: [{ when: { op: 'is_true', path: 'ok' }, next: 'say' }], default: 'finish' },
		say: { type: 'output', channel: 'transcript', message: 'Thank you.', next: 'finish' },
		finish: { type: 'end', status: 'success', outcome: 'all_done' }
	});
	const rows = stateRows(processToGraph(process).nodes);

	it('lists only the numbered boxes, leaving out the start dot, the diamond and the end dot', () => {
		expect(rows).toEqual([
			{ stateId: 'ask', title: 'Is it right?', number: 1 },
			{ stateId: 'say', title: 'Thank you.', number: 2 }
		]);
	});

	it('has the same rows as the numbered boxes of every real process, numbered from 1 with no gaps', () => {
		for (const example of workflowExamples) {
			for (const real of Object.values(example.workflow?.processes ?? {})) {
				const graph = processToGraph(real);
				const numbers = stateRows(graph.nodes).map((row) => row.number);

				expect(numbers, real.process_id).toEqual(numbers.map((_, index) => index + 1));
				expect(numbers.length, real.process_id).toBe(stepCount(graph));
			}
		}
	});
});
