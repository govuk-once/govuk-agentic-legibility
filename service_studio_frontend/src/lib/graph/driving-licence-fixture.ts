import { MarkerType } from '@xyflow/svelte';
import type { JourneyEdge, JourneyGraphElements, JourneyNode, StepNode } from './types';

// Svelte Flow requires every node to have a position before Dagre replaces these placeholders with calculated coordinates.
const initialPosition = { x: 0, y: 0 };
const markerEnd = { type: MarkerType.ArrowClosed, color: '#505a5f' };
type BranchAppearance = 'positive' | 'negative';

/* Currently this does not use the canonical schema. It is a simplified structure to display the simple DVLA driving licence service.
	This is just whilst the graphical aesthetics are resolved and the drag, edit features of the nodes are worked on.
	This static representation will then be replaced
*/
const stepNodes: StepNode[] = [
	{
		id: 'step-1',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-1',
			stepNumber: 1,
			title: 'Sign in with One Login',
			description: 'Identity check'
		},
		ariaLabel: 'Step 1, Sign in with One Login'
	},
	{
		id: 'step-2',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-2',
			stepNumber: 2,
			title: 'Confirm your identity',
			description: 'DVLA record match'
		},
		ariaLabel: 'Step 2, Confirm your identity'
	},
	{
		id: 'step-3',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-3',
			stepNumber: 3,
			title: 'Enter your licence details',
			description: 'Editing, 8 questions',
			appearance: 'editing'
		},
		selected: true,
		ariaLabel: 'Step 3, Enter your licence details, editing'
	},
	{
		id: 'step-4',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-4',
			stepNumber: 4,
			title: 'Upload evidence photo',
			description: 'File upload'
		},
		ariaLabel: 'Step 4, Upload evidence photo'
	},
	{
		id: 'step-5',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-5',
			stepNumber: 5,
			title: 'Check your answers',
			description: 'Review before submitting'
		},
		ariaLabel: 'Step 5, Check your answers'
	},
	{
		id: 'step-6',
		type: 'step',
		position: initialPosition,
		data: {
			stepId: 'step-6',
			stepNumber: 6,
			title: 'Submit and confirm',
			description: 'Posted in 2 to 3 weeks'
		},
		ariaLabel: 'Step 6, Submit and confirm'
	}
];

const terminalNodes: JourneyNode[] = [
	{
		id: 'start',
		type: 'terminal',
		position: initialPosition,
		data: { label: 'Start', appearance: 'start' },
		ariaLabel: 'Journey start'
	},
	{
		id: 'end',
		type: 'terminal',
		position: initialPosition,
		data: { label: 'End', appearance: 'end' },
		ariaLabel: 'Journey end'
	}
];

/**
 * Creates a consistent read only connection so selection and deletion safeguards are applied in one place. Branch outcome data selects the custom GOV.UK tag label when required.
 */
function createEdge(
	id: string,
	source: string,
	target: string,
	label?: string,
	branchAppearance?: BranchAppearance
): JourneyEdge {
	return {
		id,
		source,
		target,
		label,
		type: branchAppearance ? 'branch' : 'smoothstep',
		data: branchAppearance ? { appearance: branchAppearance } : undefined,
		markerEnd,
		selectable: false,
		deletable: false
	};
}

/**
 * Creates graph data with either complete branch paths or one ordered sequence. Each call returns isolated data so graph interactions cannot alter the reusable fixture.
 */
export function createDrivingLicenceGraph(showBranching: boolean): JourneyGraphElements {
	// Clone the fixture because graph selection and movement can mutate node objects during the review session.
	const nodes = structuredClone([...terminalNodes, ...stepNodes]);

	if (!showBranching) {
		// Build one ordered path through every service step because hiding branches must also remove condition and bypass nodes.
		const sequence = ['start', ...stepNodes.map((node) => node.id), 'end'];
		const edges = sequence.slice(0, -1).map((source, index) =>
			createEdge(`sequence-${index + 1}`, source, sequence[index + 1])
		);

		return { nodes, edges };
	}

	// Add a condition and visible bypass node so both outcomes can rejoin at step 5 without implying that step 4 ran.
	nodes.push(
		{
			id: 'condition-licence-record',
			type: 'condition',
			position: initialPosition,
			data: { question: 'Licence record found?' },
			ariaLabel:
				'Condition, licence record found. No leads to upload evidence photo. Yes bypasses step 4 and leads to check your answers.'
		},
		{
			id: 'step-4-bypassed',
			type: 'step',
			position: initialPosition,
			data: {
				title: 'Step 4 bypassed',
				description: 'Goes straight to step 5',
				appearance: 'bypassed'
			},
			ariaLabel: 'Step 4 bypassed, goes straight to step 5'
		}
	);

	// Define both paths explicitly so Dagre can place the split and merge from complete connection data.
	return {
		nodes,
		edges: [
			createEdge('start-step-1', 'start', 'step-1'),
			createEdge('step-1-step-2', 'step-1', 'step-2'),
			createEdge('step-2-step-3', 'step-2', 'step-3'),
			createEdge('step-3-condition', 'step-3', 'condition-licence-record'),
			createEdge('condition-step-4', 'condition-licence-record', 'step-4', 'No', 'negative'),
			createEdge('condition-bypass', 'condition-licence-record', 'step-4-bypassed', 'Yes', 'positive'),
			createEdge('step-4-step-5', 'step-4', 'step-5'),
			createEdge('bypass-step-5', 'step-4-bypassed', 'step-5'),
			createEdge('step-5-step-6', 'step-5', 'step-6'),
			createEdge('step-6-end', 'step-6', 'end')
		]
	};
}
