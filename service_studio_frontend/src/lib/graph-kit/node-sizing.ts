// The two sizes a step's box is drawn at. A standard box is the usual one. A compact box has less space around
// its words and may be narrower, for a step that is drawn smaller than the others.
export type StepNodeSize = 'standard' | 'compact';

// These must match the step node's CSS: the vertical padding of each size matches .journey-step-node and
// .journey-step-node--compact in StepNode.svelte. Kept together so a future change to one is a reminder to
// update the other.
const STEP_NODE_SIZES: Record<StepNodeSize, { minWidth: number; verticalPadding: number; minHeight: number }> = {
	standard: { minWidth: 260, verticalPadding: 20, minHeight: 56 },
	compact: { minWidth: 200, verticalPadding: 10, minHeight: 40 }
};

// These also match the step node's CSS: the horizontal padding matches .journey-step-node, and the line height
// matches the govuk-heading-s type size used there. They are the same for both sizes.
const STEP_NODE_MAX_WIDTH = 420;
const STEP_NODE_HORIZONTAL_PADDING = 30;
const STEP_NODE_TITLE_LINE_HEIGHT = 25;
// An approximate width per character, rather than a real text measurement, is enough to size a box that a
// line clamp can then cap cleanly if a title is still longer than this estimate expects.
const TITLE_AVERAGE_CHARACTER_WIDTH = 10;
const MAX_WRAPPED_LINES = 2;

/**
 * Estimates how many lines the title will wrap onto at the given width, so a node's box can be sized to
 * fit its own title rather than every node sharing one fixed height. Capped at MAX_WRAPPED_LINES because
 * the node itself line clamps at that many lines, so any additional estimated lines would not change the
 * rendered height.
 * todo: needs updating to be more scalable beyond this initial prototype
 */
function estimateWrappedLineCount(text: string, availableWidth: number): number {
	if (!text) return 0;
	const charactersPerLine = Math.max(1, Math.floor(availableWidth / TITLE_AVERAGE_CHARACTER_WIDTH));
	const lineCount = Math.ceil(text.length / charactersPerLine);
	return Math.min(MAX_WRAPPED_LINES, Math.max(1, lineCount));
}

/**
 * Works out how wide a step's box needs to be to fit its own title on one line, instead of every step
 * node sharing one fixed width regardless of how short or long its title is. Clamped between a minimum,
 * so short titles do not produce an unreadably narrow box, and a maximum, beyond which the title wraps
 * and the line clamp on the rendered node takes over instead of the box growing indefinitely. A compact box
 * has a smaller minimum, so a short title gives a narrower box.
 */
export function estimateStepNodeWidth(title: string, size: StepNodeSize = 'standard'): number {
	const naturalWidth = title.length * TITLE_AVERAGE_CHARACTER_WIDTH + STEP_NODE_HORIZONTAL_PADDING;
	return Math.min(STEP_NODE_MAX_WIDTH, Math.max(STEP_NODE_SIZES[size].minWidth, naturalWidth));
}

/**
 * Works out how tall a step's box needs to be for its own title at the given width. The node shows only
 * the title, so a single line title lands on the minimum height and a wrapped title is a little
 * taller. A box that shows extra lines below its title, such as the link that opens a sub process,
 * passes how many so the box grows to hold them. A compact box has less space above and below its words.
 */
export function estimateStepNodeHeight(title: string, width: number, extraLines = 0, size: StepNodeSize = 'standard'): number {
	const innerWidth = width - STEP_NODE_HORIZONTAL_PADDING;
	const titleLines = estimateWrappedLineCount(title, innerWidth);
	const { minHeight, verticalPadding } = STEP_NODE_SIZES[size];

	return Math.max(minHeight, verticalPadding + (titleLines + extraLines) * STEP_NODE_TITLE_LINE_HEIGHT);
}
