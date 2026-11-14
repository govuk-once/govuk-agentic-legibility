import { describe, expect, it } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import type { Process } from '$lib/schema/workflow/process';
import type { ProcessEdge } from '../process-graph-types';
import { routesOf } from '$lib/schema/workflow/routes';
import { stateRows, targetOptions } from '../state-rows';
import { graphShape, isErrorRoute, processToGraph, separateEndDots, startNodeId, stepCount, visibleGraph } from '../process-to-graph';

const finish = { state_type: 'end', status: 'success' };
const isTrue = { op: 'is_true', path: 'a' };

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

describe('processToGraph with the real examples', () => {
	const processes = serviceExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

	it('builds a graph for every process in both examples', () => {
		expect(processes).toHaveLength(14);
	});

	it('makes one node per state plus the start dot, and one edge per route plus the start edge', () => {
		for (const process of processes) {
			const graph = processToGraph(process);
			const routeCount = Object.values(process.states).flatMap((state) => routesOf(state)).length;

			expect(graph.nodes, process.process_id).toHaveLength(Object.keys(process.states).length + 1);
			expect(graph.edges, process.process_id).toHaveLength(routeCount + 1);
		}
	});

	it('gives every node and edge a unique id and joins every edge to nodes that exist', () => {
		for (const process of processes) {
			const { nodes, edges } = processToGraph(process);
			const nodeIds = new Set(nodes.map((node) => node.id));

			expect(nodeIds.size, process.process_id).toBe(nodes.length);
			expect(new Set(edges.map((edge) => edge.id)).size, process.process_id).toBe(edges.length);
			for (const edge of edges) {
				expect(nodeIds.has(edge.source), edge.id).toBe(true);
				expect(nodeIds.has(edge.target), edge.id).toBe(true);
			}
		}
	});

	it('starts with the start dot and then the start state of the process', () => {
		for (const process of processes) {
			const { nodes } = processToGraph(process);
			expect(nodes[0].id).toBe(startNodeId);
			expect(nodes[1].id).toBe(process.start);
		}
	});
});

describe('processToGraph nodes', () => {
	const process = build('ask', {
		ask: { state_type: 'input', prompt: 'Is your address correct?', schema: { kind: 'boolean' }, assign: 'ok', next: 'check' },
		check: {
			state_type: 'choice',
			name: 'Address correct?',
			rules: [{ when: isTrue, next: 'say_thanks' }],
			default: 'look_up_address'
		},
		look_up_address: { state_type: 'api_call', method: 'GET', service: 'dvla', url: '/x', next: 'finish' },
		say_thanks: { state_type: 'output', channel: 'transcript', message: 'Thank you.', next: 'finish' },
		finish: { state_type: 'end', status: 'success', outcome: 'address_confirmed' }
	});
	const { nodes } = processToGraph(process);
	const node = (id: string) => nodes.find((candidate) => candidate.id === id)!;

	it('uses the question as the title of an input', () => {
		expect(node('ask').data).toMatchObject({ title: 'Is your address correct?', stepNumber: 1, stateType: 'input' });
	});

	it('uses the message as the title of an output', () => {
		expect(node('say_thanks').data).toMatchObject({ title: 'Thank you.', stateType: 'output' });
	});

	it('tidies the code into words for a state with no text of its own', () => {
		expect(node('look_up_address').data).toMatchObject({ title: 'Look up address', stateType: 'api_call' });
	});

	it('prefers a name written by the author to the state text', () => {
		const named = processToGraph(
			build('ask', {
				ask: { state_type: 'input', name: 'Confirm address', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok', next: 'finish' },
				finish
			})
		);
		expect(named.nodes[1].data).toMatchObject({ title: 'Confirm address' });
	});

	it('draws a choice as a diamond and an end as a dot', () => {
		expect(node('check')).toMatchObject({ type: 'condition', data: { title: 'Address correct?' } });
		expect(node('finish')).toMatchObject({
			type: 'terminal',
			data: { appearance: 'end', status: 'success', stateId: 'finish', ariaLabel: 'Journey end, Address confirmed' }
		});
	});

	it('numbers only the boxes, in journey order with a choice rule before its default', () => {
		const numbered = nodes.flatMap((candidate) => (candidate.type === 'step' ? [[candidate.id, candidate.data.stepNumber]] : []));
		expect(numbered).toEqual([
			['ask', 1],
			['say_thanks', 2],
			['look_up_address', 3]
		]);
	});

	it('gives each box a size that fits its title', () => {
		const step = node('ask');
		expect(step.type === 'step' && step.data.width).toBeGreaterThanOrEqual(260);
		expect(step.type === 'step' && step.data.height).toBeGreaterThanOrEqual(56);
	});

	it('words the label read by a screen reader from the number and the title', () => {
		expect(node('ask').data.ariaLabel).toBe('Step 1, Is your address correct?');
		expect(node('check').data.ariaLabel).toBe('Decision, Address correct?');
	});

	it('lets an invoke box open the process it runs, in a taller box that says so', () => {
		const graph = processToGraph(
			build('run', {
				run: { state_type: 'invoke', process: 'photo_update', next: 'later' },
				later: { state_type: 'wait', duration: 'PT1S', next: 'done' },
				done: finish
			})
		);
		const [invoke, wait] = graph.nodes.slice(1);

		expect(invoke.data).toMatchObject({
			opensProcess: { id: 'photo_update', title: 'Photo update' },
			ariaLabel: 'Step 1, Run, opens the Photo update process'
		});
		expect(wait.data).not.toHaveProperty('opensProcess', expect.anything());
		expect(invoke.type === 'step' && wait.type === 'step' && invoke.data.height > wait.data.height).toBe(true);
	});

	it('lists a state that nothing leads to last, still numbered', () => {
		const withOrphan = processToGraph(build('a', { a: { state_type: 'wait', duration: 'PT1S', next: 'done' }, orphan_step: { state_type: 'wait', duration: 'PT1S', next: 'done' }, done: finish }));
		expect(withOrphan.nodes.map((candidate) => candidate.id)).toEqual([startNodeId, 'a', 'done', 'orphan_step']);
	});
});

describe('processToGraph edges', () => {
	const process = build('ask', {
		ask: {
			state_type: 'input',
			prompt: 'Name?',
			schema: { kind: 'string' },
			assign: 'name',
			next: 'branch',
			on_invalid: 'ask',
			timeout: { after: 'PT5S', next: 'finish' }
		},
		branch: { state_type: 'choice', rules: [{ when: isTrue, next: 'call' }], default: 'finish' },
		call: { state_type: 'api_call', method: 'GET', service: 'dvla', url: '/x', catch: [{ on: 'any', next: 'finish' }], next: 'finish' },
		finish
	});
	const { edges } = processToGraph(process);

	it('starts from the start dot', () => {
		expect(edges[0]).toMatchObject({ source: startNodeId, target: 'ask', data: { kind: 'start' } });
	});

	it('gives each route the kind it belongs to', () => {
		const kinds = edges.map((edge) => [edge.source, edge.target, edge.data?.kind]);
		expect(kinds).toEqual([
			[startNodeId, 'ask', 'start'],
			['ask', 'branch', 'next'],
			['ask', 'ask', 'on_invalid'],
			['ask', 'finish', 'timeout'],
			['branch', 'call', 'rule'],
			['branch', 'finish', 'default'],
			['call', 'finish', 'next'],
			['call', 'finish', 'catch']
		]);
	});

	it('keeps two routes to the same state apart with different ids', () => {
		const toFinish = edges.filter((edge) => edge.source === 'call' && edge.target === 'finish');
		expect(toFinish.map((edge) => edge.id)).toEqual(['call:next', 'call:catch.0.next']);
	});

	it('draws no edge for a route to a state that does not exist or a start that does not exist', () => {
		const half = processToGraph(build('a', { a: { state_type: 'wait', duration: 'PT1S', next: 'missing' } }));
		expect(half.edges).toHaveLength(1);

		const noStart = processToGraph(build('nowhere', { a: finish }));
		expect(noStart.edges).toEqual([]);
	});
});

describe('isErrorRoute', () => {
	const edge = (kind: string) => ({ id: kind, source: 'a', target: 'b', data: { kind } }) as ProcessEdge;

	it.each(['catch', 'timeout', 'on_invalid'])('treats a %s route as an error route', (kind) => {
		expect(isErrorRoute(edge(kind))).toBe(true);
	});

	it.each(['start', 'next', 'rule', 'default'])('treats a %s route as part of the main journey', (kind) => {
		expect(isErrorRoute(edge(kind))).toBe(false);
	});

	it('picks out only the error routes of a real process', () => {
		const process = serviceExamples[0].workflow!.processes[serviceExamples[0].workflow!.manifest.entry];
		const { edges } = processToGraph(process);
		const errorCount = edges.filter(isErrorRoute).length;

		expect(errorCount).toBeGreaterThan(0);
		expect(errorCount).toBeLessThan(edges.length);
	});
});

describe('stepCount', () => {
	it('counts only the numbered boxes, not the diamonds or the dots', () => {
		const graph = processToGraph(
			build('ask', {
				ask: { state_type: 'input', prompt: 'Q', schema: { kind: 'boolean' }, assign: 'a', next: 'check' },
				check: { state_type: 'choice', rules: [{ when: isTrue, next: 'finish' }], default: 'finish' },
				finish
			})
		);
		expect(graph.nodes).toHaveLength(4);
		expect(stepCount(graph)).toBe(1);
	});
});

describe('visibleGraph', () => {
	// A call whose error route leads to a recovery step and an end that nothing else reaches.
	const process = build('call', {
		call: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'done', catch: [{ on: 'any', next: 'sorry' }] },
		sorry: { state_type: 'output', channel: 'transcript', message: 'Sorry.', next: 'failed' },
		failed: { state_type: 'end', status: 'failed' },
		done: finish,
		unused: finish
	});
	const graph = processToGraph(process);

	it('gives the whole graph when error routes are on', () => {
		expect(visibleGraph(graph, { showErrorRoutes: true })).toBe(graph);
	});

	it('removes the error routes and every state only they lead to when error routes are off', () => {
		const shown = visibleGraph(graph, { showErrorRoutes: false });

		expect(shown.nodes.map((node) => node.id)).toEqual([startNodeId, 'call', 'done', 'unused']);
		expect(shown.edges.map((edge) => edge.id)).toEqual([`${startNodeId}:start`, 'call:next']);
	});

	it('keeps a state that nothing leads to, because that is a problem worth seeing', () => {
		expect(visibleGraph(graph, { showErrorRoutes: false }).nodes.map((node) => node.id)).toContain('unused');
	});

	it('keeps a state that the main journey also reaches', () => {
		const shared = processToGraph(
			build('call', {
				call: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'done', catch: [{ on: 'any', next: 'done' }] },
				done: finish
			})
		);
		expect(visibleGraph(shared, { showErrorRoutes: false }).nodes.map((node) => node.id)).toEqual([startNodeId, 'call', 'done']);
	});
});

describe('visibleGraph with the real examples', () => {
	const processes = serviceExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

	it('numbers the steps that are shown from 1 with no gaps, with error routes on or off', () => {
		for (const process of processes) {
			for (const showErrorRoutes of [true, false]) {
				const numbers = visibleGraph(processToGraph(process), { showErrorRoutes }).nodes.flatMap((node) =>
					node.type === 'step' ? [node.data.stepNumber] : []
				);
				expect(numbers, `${process.process_id} ${showErrorRoutes}`).toEqual(numbers.map((_, index) => index + 1));
			}
		}
	});

	it('leaves a dot floating on its own only when no route at all leads to it', () => {
		for (const process of processes) {
			const graph = processToGraph(process);
			const shown = visibleGraph(graph, { showErrorRoutes: false });
			const touched = new Set(shown.edges.flatMap((edge) => [edge.source, edge.target]));
			const floating = shown.nodes.filter((node) => node.id !== startNodeId && !touched.has(node.id));

			// A state with no route into it, even an error route, is a real problem in the example and is kept.
			for (const node of floating) {
				expect(graph.edges.some((edge) => edge.target === node.id), `${process.process_id}: ${node.id}`).toBe(false);
			}
		}
	});
});

describe('separateEndDots', () => {
	// Two steps lead to the same end state, and a third leads to an end state of its own.
	const graph = processToGraph(
		build('first', {
			first: { state_type: 'wait', duration: 'PT1S', next: 'second' },
			second: { state_type: 'choice', rules: [{ when: isTrue, next: 'shared' }], default: 'third' },
			third: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'shared', catch: [{ on: 'any', next: 'shared' }] },
			shared: { state_type: 'end', status: 'success', outcome: 'done' },
			alone: finish
		})
	);
	const separated = separateEndDots(graph);

	it('draws one end dot for each step that leads to a shared end state', () => {
		const dots = separated.nodes.filter((node) => node.type === 'terminal' && node.data.stateId === 'shared');
		expect(dots.map((dot) => dot.id)).toEqual(['shared#second', 'shared#third']);
	});

	it('points each route at the dot under the step it leaves, and shares a dot between two routes from one step', () => {
		const targets = separated.edges.filter((edge) => edge.target.startsWith('shared')).map((edge) => [edge.source, edge.target]);
		expect(targets).toEqual([
			['second', 'shared#second'],
			['third', 'shared#third'],
			['third', 'shared#third']
		]);
	});

	it('keeps the state id on every copy so choosing one selects the same state', () => {
		const dots = separated.nodes.filter((node) => node.type === 'terminal' && node.data.stateId === 'shared');
		for (const dot of dots) expect(dot.data).toMatchObject({ stateId: 'shared', status: 'success', appearance: 'end' });
	});

	it('leaves an end state with no route or one route into it as it is', () => {
		expect(separated.nodes.some((node) => node.id === 'alone')).toBe(true);
		const single = separateEndDots(processToGraph(build('a', { a: { state_type: 'wait', duration: 'PT1S', next: 'done' }, done: finish })));
		expect(single.nodes.map((node) => node.id)).toEqual([startNodeId, 'a', 'done']);
	});

	it('gives the same number of boxes and lines and does not change the step count', () => {
		expect(separated.edges).toHaveLength(graph.edges.length);
		expect(stepCount(separated)).toBe(stepCount(graph));
	});
});

describe('graphShape', () => {
	const states = {
		ask: { state_type: 'input', prompt: 'Name?', schema: { kind: 'string' }, assign: 'name', next: 'done' },
		done: finish
	};

	it('stays the same when only a title changes', () => {
		const renamed = { ...states, ask: { ...states.ask, name: 'A new title' } };
		expect(graphShape(processToGraph(build('ask', renamed)))).toBe(graphShape(processToGraph(build('ask', states))));
	});

	it('changes when a line is moved to a different place', () => {
		const moved = { ...states, ask: { ...states.ask, next: 'other' }, other: finish };
		expect(graphShape(processToGraph(build('ask', moved)))).not.toBe(graphShape(processToGraph(build('ask', { ...states, other: finish }))));
	});

	it('changes when a state is added', () => {
		expect(graphShape(processToGraph(build('ask', { ...states, extra: finish })))).not.toBe(graphShape(processToGraph(build('ask', states))));
	});
});

describe('developer steps', () => {
	const input = (next: string) => ({ state_type: 'input', prompt: 'A question?', schema: { kind: 'string' }, assign: 'answer', next });
	const assign = (next: string) => ({ state_type: 'assign', set: { count: 1 }, next });

	// A question, then an assign, then a second question.
	const process = build('first', {
		first: input('save'),
		save: assign('second'),
		second: input('done'),
		done: finish
	});
	const graph = processToGraph(process, ['assign']);
	const shownIds = (shown: ReturnType<typeof visibleGraph>) => shown.nodes.map((node) => node.id);

	it('marks a developer step and gives it no number, so the steps around it run on without a gap', () => {
		const numbers = graph.nodes.flatMap((node) => (node.type === 'step' ? [[node.id, node.data.stepNumber, node.data.developer]] : []));
		expect(numbers).toEqual([
			['first', 1, undefined],
			['save', undefined, true],
			['second', 2, undefined]
		]);
	});

	it('numbers every step as before when no developer types are named', () => {
		const plain = processToGraph(process);
		expect(plain.nodes.flatMap((node) => (node.type === 'step' ? [node.data.stepNumber] : []))).toEqual([1, 2, 3]);
	});

	it('draws a developer step as a compact box, which is smaller than the box it would be otherwise', () => {
		const sizeOf = (built: ReturnType<typeof processToGraph>) => {
			const save = built.nodes.find((node) => node.id === 'save');
			if (save?.type !== 'step') throw new Error('save should be a box');
			return save.data;
		};
		const compact = sizeOf(graph);
		const standard = sizeOf(processToGraph(process));

		expect(compact.compact).toBe(true);
		expect(standard.compact).toBeUndefined();
		expect(compact.width).toBeLessThan(standard.width);
		expect(compact.height).toBeLessThan(standard.height);
	});

	it('does not count a developer step as a step, or list it or give it a number in the choices', () => {
		expect(stepCount(graph)).toBe(2);
		expect(stateRows(graph.nodes).map((row) => row.stateId)).toEqual(['first', 'second']);
		expect(targetOptions(graph.nodes).find((option) => option.stateId === 'save')?.label).toBe('Save');
	});

	it('shows the whole graph when developer steps are on', () => {
		expect(visibleGraph(graph, { showErrorRoutes: true, showDeveloperSteps: true })).toBe(graph);
	});

	it('leaves the developer step out and draws the line past it, keeping the route the line came from', () => {
		const shown = visibleGraph(graph, { showErrorRoutes: true, showDeveloperSteps: false });

		expect(shownIds(shown)).toEqual([startNodeId, 'first', 'second', 'done']);
		const past = shown.edges.find((edge) => edge.source === 'first');
		expect(past).toMatchObject({ id: 'first:next', target: 'second', data: { kind: 'next', path: ['next'] } });
		expect(shown.edges.some((edge) => edge.source === 'save' || edge.target === 'save')).toBe(false);
	});

	it('passes over several developer steps in a row', () => {
		const chain = processToGraph(build('first', { first: input('a'), a: assign('b'), b: assign('second'), second: input('done'), done: finish }), ['assign']);
		const shown = visibleGraph(chain, { showErrorRoutes: true, showDeveloperSteps: false });

		expect(shown.edges.find((edge) => edge.source === 'first')?.target).toBe('second');
	});

	it('moves the start line on when the start itself is a developer step', () => {
		const shown = visibleGraph(
			processToGraph(build('save', { save: assign('second'), second: input('done'), done: finish }), ['assign']),
			{ showErrorRoutes: true, showDeveloperSteps: false }
		);

		expect(shown.edges.find((edge) => edge.source === startNodeId)?.target).toBe('second');
	});

	it('drops the line before a developer step that leads nowhere', () => {
		const loose = processToGraph(build('first', { first: input('save'), save: { state_type: 'assign', set: { count: 1 } } }), ['assign']);
		const shown = visibleGraph(loose, { showErrorRoutes: true, showDeveloperSteps: false });

		expect(shown.edges.map((edge) => edge.id)).toEqual([`${startNodeId}:start`]);
	});

	it('ends and drops the line when developer steps only lead round to each other', () => {
		const loop = processToGraph(build('first', { first: input('a'), a: assign('b'), b: assign('a') }), ['assign']);
		const shown = visibleGraph(loop, { showErrorRoutes: true, showDeveloperSteps: false });

		expect(shown.edges.map((edge) => edge.id)).toEqual([`${startNodeId}:start`]);
	});

	it('gives each line its own id when a developer step leads on to more than one state', () => {
		const twoWays = processToGraph(
			build('first', {
				first: input('call'),
				call: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'done', catch: [{ on: 'any', next: 'sorry' }] },
				sorry: finish,
				done: finish
			}),
			['api_call']
		);
		const shown = visibleGraph(twoWays, { showErrorRoutes: true, showDeveloperSteps: false });

		expect(shown.edges.filter((edge) => edge.source === 'first').map((edge) => [edge.id, edge.target])).toEqual([
			['first:next>done', 'done'],
			['first:next>sorry', 'sorry']
		]);
	});

	it('can hide error routes and developer steps together', () => {
		// The first question sends an invalid answer to a sorry end, and carries on through an assign to done.
		const withError = processToGraph(
			build('first', {
				first: { ...input('save'), on_invalid: 'sorry' },
				save: assign('done'),
				done: finish,
				sorry: finish
			}),
			['assign']
		);
		const shown = visibleGraph(withError, { showErrorRoutes: false, showDeveloperSteps: false });

		expect(shown.nodes.map((node) => node.id)).toEqual([startNodeId, 'first', 'done']);
		expect(shown.edges.map((edge) => [edge.id, edge.target])).toEqual([
			[`${startNodeId}:start`, 'first'],
			['first:next', 'done']
		]);
	});

	describe('with the real examples', () => {
		const processes = serviceExamples.flatMap((example) => Object.values(example.workflow?.processes ?? {}));

		it('is exercised by at least one real process that has an assign state', () => {
			expect(processes.some((process) => Object.values(process.states).some((state) => state.state_type === 'assign'))).toBe(true);
		});

		it('hides every assign, leaves no line to a hidden box, and numbers the steps left from 1 with no gaps', () => {
			for (const process of processes) {
				const shown = visibleGraph(processToGraph(process, ['assign']), { showErrorRoutes: true, showDeveloperSteps: false });
				const ids = new Set(shown.nodes.map((node) => node.id));

				for (const [code, state] of Object.entries(process.states)) {
					if (state.state_type === 'assign') expect(ids.has(code), `${process.process_id}: ${code}`).toBe(false);
				}
				for (const edge of shown.edges) {
					expect(ids.has(edge.source) && ids.has(edge.target), `${process.process_id}: ${edge.id}`).toBe(true);
				}
				const numbers = shown.nodes.flatMap((node) => (node.type === 'step' ? [node.data.stepNumber] : []));
				expect(numbers, process.process_id).toEqual(numbers.map((_, index) => index + 1));
			}
		});
	});
});
