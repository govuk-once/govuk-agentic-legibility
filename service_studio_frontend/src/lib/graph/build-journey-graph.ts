import type { JourneyStep } from '$lib/journey/types';
import type { BranchDecoration, JourneyEdge, JourneyGraphElements, JourneyNode, StepNode } from './types';

// A placeholder coordinate every node is created with, replaced by the real top left position once
// layoutJourneyGraph runs. Kept as a shared constant so the builder never has to invent a value.
const initialPosition = { x: 0, y: 0 };

// These must match the step node's CSS: the horizontal padding matches .journey-step-node in
// StepNode.svelte, and the line heights match the govuk-heading-s and govuk-body-s type sizes used
// there. Kept together so a future change to one is a reminder to update the other.
const STEP_NODE_MIN_WIDTH = 260;
const STEP_NODE_MAX_WIDTH = 420;
const STEP_NODE_HORIZONTAL_PADDING = 30;
const STEP_NODE_VERTICAL_PADDING = 20;
const STEP_NODE_TITLE_LINE_HEIGHT = 25;
const STEP_NODE_DESCRIPTION_LINE_HEIGHT = 20;
const STEP_NODE_TITLE_GAP = 4;
const STEP_NODE_MIN_HEIGHT = 78;
// An approximate width per character, rather than a real text measurement, is enough to size a box that a
// line-clamp can then cap cleanly if a title or description is still longer than this estimate expects.

const TITLE_AVERAGE_CHARACTER_WIDTH = 10;
const DESCRIPTION_AVERAGE_CHARACTER_WIDTH = 8;
const MAX_WRAPPED_LINES = 2;

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
 * Estimates how many lines this text will wrap onto at the given width, so a node's box can be sized to
 * fit its own content rather than every node sharing one fixed height. Capped at MAX_WRAPPED_LINES because the node itself line clamps at that many
 * lines, so any additional estimated lines would not change the rendered height.
 * todo: needs updating to be more scalable beyond this initial prototype
 */
function estimateWrappedLineCount(text: string, availableWidth: number, averageCharacterWidth: number): number {
	if (!text) return 0;
	const charactersPerLine = Math.max(1, Math.floor(availableWidth / averageCharacterWidth));
	const lineCount = Math.ceil(text.length / charactersPerLine);
	return Math.min(MAX_WRAPPED_LINES, Math.max(1, lineCount));
}

/**
 * Works out how wide a step's box needs to be to fit its own title on one line, instead of every step
 * node sharing one fixed width regardless of how short or long its title is. Clamped between a minimum,
 * so short titles do not produce an unreadably narrow box, and a maximum, beyond which the title wraps
 * and the line clamp on the rendered node takes over instead of the box growing indefinitely.
 */
function estimateStepNodeWidth(title: string): number {
	const naturalWidth = title.length * TITLE_AVERAGE_CHARACTER_WIDTH + STEP_NODE_HORIZONTAL_PADDING;
	return Math.min(STEP_NODE_MAX_WIDTH, Math.max(STEP_NODE_MIN_WIDTH, naturalWidth));
}

/**
 * Works out how tall a step's box needs to be for its own title and description at the given width,
 * instead of every step node using one fixed height regardless of text length.
 */
function estimateStepNodeHeight(title: string, description: string, width: number): number {
	const innerWidth = width - STEP_NODE_HORIZONTAL_PADDING;
	const titleLines = estimateWrappedLineCount(title, innerWidth, TITLE_AVERAGE_CHARACTER_WIDTH);
	const descriptionLines = estimateWrappedLineCount(description, innerWidth, DESCRIPTION_AVERAGE_CHARACTER_WIDTH);
	const contentHeight =
		titleLines * STEP_NODE_TITLE_LINE_HEIGHT + STEP_NODE_TITLE_GAP + descriptionLines * STEP_NODE_DESCRIPTION_LINE_HEIGHT;

	return Math.max(STEP_NODE_MIN_HEIGHT, STEP_NODE_VERTICAL_PADDING + contentHeight);
}

/**
 * Builds one graph node per journey step, taking the step number from its position in the list so
 * numbering always matches the current order rather than a stored value that could go stale.
 */
function buildStepNodes(steps: JourneyStep[]): StepNode[] {
	return steps.map((step, index) => {
		const titleWithNumber = `${index + 1}. ${step.title}`;
		const width = estimateStepNodeWidth(titleWithNumber);
		return {
			id: step.id,
			type: 'step',
			position: initialPosition,
			data: {
				stepId: step.id,
				stepNumber: index + 1,
				title: step.title,
				description: step.description,
				width,
				height: estimateStepNodeHeight(titleWithNumber, step.description, width)
			},
			ariaLabel: `Step ${index + 1}, ${step.title}`
		};
	});
}

/**
 * Creates one connection between two nodes. A tag colour marks the connection as a branch outcome, which
 * is what selects the labelled GOV.UK tag drawn on it, so ordinary sequence steps pass no tag colour.
 */
function createEdge(id: string, source: string, target: string, label?: string, tagColour?: string): JourneyEdge {
	return {
		id,
		source,
		target,
		label,
		kind: tagColour ? 'branch' : 'sequence',
		...(tagColour ? { tagColour } : {})
	};
}

/**
 * Builds a plain, unbranched chain through every step in order. Used both when branching is turned off
 * and as the fallback when a branch decoration's position no longer has enough steps around it to form a
 * branch, which can happen once steps are removed or reordered.
 */
function buildSequentialGraph(steps: JourneyStep[]): JourneyGraphElements {
	const nodes = structuredClone([...terminalNodes, ...buildStepNodes(steps)]);
	const sequence = ['start', ...steps.map((step) => step.id), 'end'];
	const edges = sequence
		.slice(0, -1)
		.map((source, index) => createEdge(`sequence-${index + 1}`, source, sequence[index + 1]));

	return { nodes, edges };
}

/*
	This does not use the canonical schema right now. It is a simplified structure standing in for the real branching
	while the graphical aesthetics, drag and edit features of the nodes are worked on. The branch
	point is resolved entirely from the current position of the steps, using the BranchDecoration passed
	in alongside them, rather than from a step's own branchesTo text or a fixed step id, so that reordering
	steps in the list also reorders the graph. This is intentionally not a real branching implementation, that is
	schema work this static representation will later be replaced by.
*/
export function createJourneyGraph(
	steps: JourneyStep[],
	showBranching: boolean,
	branchDecoration: BranchDecoration
): JourneyGraphElements {
	if (!showBranching) {
		return buildSequentialGraph(steps);
	}

	const { afterIndex, question, branchLabels } = branchDecoration;
	const anchorStep = steps[afterIndex];
	const branchSteps = [steps[afterIndex + 1], steps[afterIndex + 2]];
	const mergeStep = steps[afterIndex + 3];

	// Fall back to a plain sequence if there are not enough steps at and after this position to form a
	// branch and rejoin it, which is not an error, just nothing left to draw as a branch.
	if (!anchorStep || !branchSteps[0] || !branchSteps[1] || !mergeStep) {
		return buildSequentialGraph(steps);
	}

	const nodes = structuredClone([...terminalNodes, ...buildStepNodes(steps)]);
	const conditionNodeId = 'branch-condition';
	nodes.push({
		id: conditionNodeId,
		type: 'condition',
		position: initialPosition,
		data: { question },
		ariaLabel: `Condition, ${question}`
	});

	const edges: JourneyEdge[] = [];

	const preSequence = ['start', ...steps.slice(0, afterIndex + 1).map((step) => step.id)];
	preSequence.slice(0, -1).forEach((source, index) => {
		edges.push(createEdge(`sequence-${index + 1}`, source, preSequence[index + 1]));
	});
	edges.push(createEdge('anchor-condition', anchorStep.id, conditionNodeId));

	branchSteps.forEach((branchStep, branchIndex) => {
		const { label, tagColour } = branchLabels[branchIndex];
		edges.push(createEdge(`condition-branch-${branchIndex + 1}`, conditionNodeId, branchStep.id, label, tagColour));
		edges.push(createEdge(`branch-${branchIndex + 1}-merge`, branchStep.id, mergeStep.id));
	});

	const postSequence = [...steps.slice(afterIndex + 3).map((step) => step.id), 'end'];
	postSequence.slice(0, -1).forEach((source, index) => {
		edges.push(createEdge(`post-sequence-${index + 1}`, source, postSequence[index + 1]));
	});

	return { nodes, edges };
}
