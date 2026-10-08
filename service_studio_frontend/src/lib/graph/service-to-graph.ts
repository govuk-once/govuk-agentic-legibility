import { humanKind } from '$lib/schema';
import type { Service, ServiceStep } from '$lib/schema';
import { estimateStepNodeHeight, estimateStepNodeWidth } from './node-sizing';
import type { JourneyEdge, JourneyGraphElements, JourneyNode } from './types';

// A placeholder coordinate every node is created with. layoutJourneyGraph replaces this on first load;
// after that the graph editor's own reconciliation keeps whatever position the node already has, new or
// dragged, so this value is only ever seen for the brief moment before either of those runs.
const initialPosition = { x: 0, y: 0 };

/**
 * Builds one graph node per service step, numbering steps by their position in the list so the number
 * always matches the current order rather than a stored value that could go stale.
 */
function buildStepNodes(steps: ServiceStep[]): JourneyNode[] {
	return steps.map((step, index) => {
		const titleWithNumber = `${index + 1}. ${step.name}`;
		const width = estimateStepNodeWidth(titleWithNumber);

		return {
			id: step.id,
			type: 'step',
			position: initialPosition,
			data: {
				stepId: step.id,
				stepNumber: index + 1,
				title: step.name,
				kind: step.type.kind,
				width,
				height: estimateStepNodeHeight(titleWithNumber, width),
				ariaLabel: `Step ${index + 1}, ${step.name}, delivered by ${humanKind(step.type.kind)}`
			}
		};
	});
}

/**
 * Turns a validated canonical service into the nodes and edges the graph renders. A step with one
 * onward transition connects straight to its target. A step with two or more gets a gateway diamond,
 * with one edge per transition, carrying that route's own label read straight from the step for display,
 * never a second place it is edited from. A step with no transitions gets its own terminal node, rather
 * than every dead end sharing one node: a real service has several distinct endings (one success, several
 * different rejections or offramps), and funnelling them all onto one shared node the same distance from
 * everywhere else in the graph is both misleading and, at real scale, the single biggest driver of a
 * layout spreading far wider than the journey actually needs.
 *
 * explicitEndStepIds, when given, restricts which of those dead ends actually draw a terminal: only a
 * step named in it is treated as a deliberate ending, everything else is left with no decoration at all.
 * The interactive editor passes this so a step that only just became a dead end as the side effect of
 * some other edit, rather than something someone actually decided, does not look like a finished part of
 * the journey until they say so. Left out entirely, every dead end draws its terminal, which is what a
 * plain read of an already saved service should show.
 */
export function serviceToGraph(service: Service, explicitEndStepIds?: Set<string>): JourneyGraphElements {
	const stepIds = new Set(service.steps.map((step) => step.id));
	const nodes: JourneyNode[] = [
		{
			id: 'start',
			type: 'terminal',
			position: initialPosition,
			data: { label: 'Start', appearance: 'start', ariaLabel: 'Journey start' }
		},
		...buildStepNodes(service.steps)
	];
	const edges: JourneyEdge[] = [];

	// Connect the entry point. startStepId is guaranteed to resolve by the schema, but guard anyway so a
	// mid-edit working copy in the editor cannot throw.
	if (stepIds.has(service.startStepId)) {
		edges.push({ id: 'edge-start', source: 'start', target: service.startStepId, data: { kind: 'sequence' } });
	}

	for (const step of service.steps) {
		const transitions = step.transitions.filter((transition) => stepIds.has(transition.targetStepId));

		if (transitions.length === 0) {
			if (explicitEndStepIds && !explicitEndStepIds.has(step.id)) continue;

			const terminalId = `end-${step.id}`;
			nodes.push({
				id: terminalId,
				type: 'terminal',
				position: initialPosition,
				data: { label: 'End', appearance: 'end', ariaLabel: `Journey end after ${step.name}` }
			});
			edges.push({
				id: `edge-${step.id}-${terminalId}`,
				source: step.id,
				target: terminalId,
				data: { kind: 'sequence' }
			});
			continue;
		}

		if (transitions.length === 1) {
			edges.push({
				id: `edge-${step.id}-${transitions[0].targetStepId}`,
				source: step.id,
				target: transitions[0].targetStepId,
				data: { kind: 'sequence' }
			});
			continue;
		}

		// Two or more onward paths: insert a gateway diamond between the step and its targets. The diamond
		// carries no text of its own, each route's label and condition are edited on the step instead.
		const gatewayId = `gateway-${step.id}`;
		nodes.push({
			id: gatewayId,
			type: 'condition',
			position: initialPosition,
			data: { ariaLabel: `Decision after ${step.name}` }
		});
		edges.push({
			id: `edge-${step.id}-${gatewayId}`,
			source: step.id,
			target: gatewayId,
			data: { kind: 'sequence' }
		});

		transitions.forEach((transition, index) => {
			edges.push({
				id: `edge-${gatewayId}-${transition.targetStepId}-${index}`,
				source: gatewayId,
				target: transition.targetStepId,
				// A read only copy of this route's own label, for display on the canvas: the step's own
				// transition remains the one place it is actually edited, see StepEditorCard.
				label: transition.label,
				data: { kind: 'branch' }
			});
		});
	}

	return { nodes, edges };
}
