// The data each of the three node shapes draws: a box, a diamond and a dot. These are the least that
// StepNode, ConditionNode and TerminalNode need, so any editor can use the shapes by giving its own nodes
// these keys and adding whatever else it needs beside them.

// A numbered box. Its width and height are worked out from its title, so each box fits its own words.
export type StepNodeData = {
	title: string;
	stepNumber?: number;
	ariaLabel: string;
	// Set when the box leads to another process. The box then shows a line offering to open it.
	opensProcess?: { id: string; title: string };
	width: number;
	height: number;
	// Set on a box that is drawn smaller and grey, so it stands back from the steps a person reads. Its width and
	// height are worked out for the compact size in node-sizing.ts.
	compact?: boolean;
	// The colour of the outline of the box, written as a CSS colour, so an editor can tell kinds of step apart.
	// Left out, the box has the usual grey outline.
	outlineColour?: string;
};

// A diamond. It carries no words of its own, only a label for a screen reader.
export type DecisionNodeData = {
	ariaLabel: string;
	// Marks a shape placed from a toolbar that is not yet joined to anything, which is drawn dashed.
	draft?: boolean;
};

// A dot for the start or the end of a journey.
export type TerminalNodeData = {
	label: string;
	appearance: 'start' | 'end';
	ariaLabel: string;
	// See DecisionNodeData.
	draft?: boolean;
};
