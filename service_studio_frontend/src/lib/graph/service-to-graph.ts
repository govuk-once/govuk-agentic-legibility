import { humanKind } from '$lib/schema';
import type { Condition, Service, ServiceStep } from '$lib/schema';
import { estimateStepNodeHeight, estimateStepNodeWidth } from './node-sizing';
import type { JourneyEdge, JourneyGraphElements, JourneyNode } from './types';

// A placeholder coordinate every node is created with, replaced by the real top left position once
// layoutJourneyGraph runs.
const initialPosition = { x: 0, y: 0 };

const OPERATOR_SYMBOLS: Record<string, string> = {
	equals: '=',
	notEquals: '≠',
	greaterThan: '>',
	lessThan: '<',
	contains: 'contains',
	in: 'in'
};

const MAX_LABEL_LENGTH = 28;

/**
 * Renders a condition into a short edge label, for example "weeks_worked >= 26". Used only when a
 * transition has a condition but no explicit label of its own.
 */
function summariseCondition(condition: Condition | undefined): string | undefined {
	if (!condition) return undefined;

	const rules = condition.all ?? condition.any ?? [];
	if (rules.length === 0) return undefined;

	const joiner = condition.all ? ' and ' : ' or ';
	const text = rules
		.map((rule) => `${rule.field} ${OPERATOR_SYMBOLS[rule.operator] ?? rule.operator} ${String(rule.value)}`)
		.join(joiner);

	return text.length > MAX_LABEL_LENGTH ? `${text.slice(0, MAX_LABEL_LENGTH - 1)}…` : text;
}

/**
 * Picks the question shown inside a gateway diamond. The canonical schema has no gateway of its own, so
 * this reads the best available wording off the step: its name if that already ends in a question mark,
 * otherwise the label of the first field that does, since that field is usually the choice the branch
 * turns on. A neutral fallback covers a step that offers neither.
 */
function deriveQuestion(step: ServiceStep): string {
	if (step.name.trim().endsWith('?')) return step.name;

	const questionField = step.fields.find((field) => field.label.trim().endsWith('?'));
	if (questionField) return questionField.label;

	return 'Which route applies?';
}

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
				height: estimateStepNodeHeight(titleWithNumber, width)
			},
			ariaLabel: `Step ${index + 1}, ${step.name}, delivered by ${humanKind(step.type.kind)}`
		};
	});
}

/**
 * Turns a validated canonical service into the nodes and edges the graph renders. A step with one
 * onward transition connects straight to its target. A step with two or more gets a gateway diamond,
 * with one edge per transition, labelled where the transition carries a label or a condition and drawn
 * as a plain line where it does not. Any step with no transitions is joined to a shared end node.
 */
export function serviceToGraph(service: Service): JourneyGraphElements {
	const stepIds = new Set(service.steps.map((step) => step.id));
	const nodes: JourneyNode[] = [
		{
			id: 'start',
			type: 'terminal',
			position: initialPosition,
			data: { label: 'Start', appearance: 'start' },
			ariaLabel: 'Journey start'
		},
		...buildStepNodes(service.steps)
	];
	const edges: JourneyEdge[] = [];

	// Connect the entry point. startStepId is guaranteed to resolve by the schema, but guard anyway so a
	// mid-edit working copy in the editor cannot throw.
	if (stepIds.has(service.startStepId)) {
		edges.push({ id: 'edge-start', source: 'start', target: service.startStepId, kind: 'sequence' });
	}

	let needsEndNode = false;

	for (const step of service.steps) {
		const transitions = step.transitions.filter((transition) => stepIds.has(transition.targetStepId));

		if (transitions.length === 0) {
			needsEndNode = true;
			edges.push({ id: `edge-${step.id}-end`, source: step.id, target: 'end', kind: 'sequence' });
			continue;
		}

		if (transitions.length === 1) {
			edges.push({
				id: `edge-${step.id}-${transitions[0].targetStepId}`,
				source: step.id,
				target: transitions[0].targetStepId,
				kind: 'sequence'
			});
			continue;
		}

		// Two or more onward paths: insert a gateway diamond between the step and its targets.
		const gatewayId = `gateway-${step.id}`;
		nodes.push({
			id: gatewayId,
			type: 'condition',
			position: initialPosition,
			data: { question: deriveQuestion(step) },
			ariaLabel: `Decision after ${step.name}`
		});
		edges.push({ id: `edge-${step.id}-${gatewayId}`, source: step.id, target: gatewayId, kind: 'sequence' });

		transitions.forEach((transition, index) => {
			const label = transition.label ?? summariseCondition(transition.condition);
			edges.push({
				id: `edge-${gatewayId}-${transition.targetStepId}-${index}`,
				source: gatewayId,
				target: transition.targetStepId,
				kind: 'branch',
				label,
				...(label ? { tagColour: 'grey' } : {})
			});
		});
	}

	if (needsEndNode) {
		nodes.push({
			id: 'end',
			type: 'terminal',
			position: initialPosition,
			data: { label: 'End', appearance: 'end' },
			ariaLabel: 'Journey end'
		});
	}

	return { nodes, edges };
}
