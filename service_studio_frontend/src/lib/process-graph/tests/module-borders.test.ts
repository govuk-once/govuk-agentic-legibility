import { describe, expect, it } from 'vitest';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { addModule } from '$lib/modules/add-module';
import { moduleBorders } from '../module-borders';
import { processToGraph } from '../process-to-graph';
import type { ProcessNode } from '../process-graph-types';

const journey: WorkingProcess = { process_id: 'test', version: '0.1.0', start: 'hello', vars: {}, states: { hello: { state_type: 'output', channel: 'transcript', message: 'Hello' } } };

// Places every node at a fixed spot by its id, so the size of a border can be worked out by hand.
const placeAt = (places: Record<string, { x: number; y: number }>) => (node: ProcessNode) => places[node.id] ?? { x: 0, y: 0 };

describe('moduleBorders', () => {
	it('draws one border round the shapes of a copy of a module, with space round them and its name', () => {
		const { process } = addModule(journey, 'boolean_decision');
		const nodes = processToGraph(process).nodes;
		const ask = nodes.find((node) => node.id === 'boolean_decision_ask');
		const [border] = moduleBorders(nodes, placeAt({ boolean_decision_ask: { x: 100, y: 100 }, boolean_decision_decide: { x: 100, y: 300 } }));

		expect(border.position).toEqual({ x: 80, y: 80 });
		expect(border.width).toBe((ask?.type === 'step' ? ask.data.width : 0) + 40);
		expect(border.data).toEqual({ label: 'Yes / No', groupId: process.states.boolean_decision_ask.metadata?.group_id });
		expect(border.selectable).toBe(false);
		// The border is only dragged by its dot.
		expect(border.dragHandle).toBe('.module-border-node__handle');
	});

	it('draws a border for each copy, and none for shapes that are not from a module', () => {
		const twice = addModule(addModule(journey, 'boolean_decision').process, 'boolean_decision').process;
		expect(moduleBorders(processToGraph(twice).nodes, placeAt({}))).toHaveLength(2);
	});

	it('draws a border round a module with only one shape as well, named with the module', () => {
		const { process } = addModule(journey, 'message');
		const borders = moduleBorders(processToGraph(process).nodes, placeAt({}));
		expect(borders.map((border) => border.data.label)).toEqual(['Message']);
	});
});
