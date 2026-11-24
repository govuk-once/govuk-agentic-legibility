import type { JourneyProblemKind } from '$lib/schema/workflow/journey-problems';

/*
	The small before and after pictures shown in the "How to fix it" column of the problems console, one for each sort
	of problem about how steps connect. Each half of a picture is two shapes joined by a line. Red shows the journey as
	it is, with the problem, and green shows it once it is fixed.

	1. A shape is a step box, a decision diamond, or a dot for the start or the end.
	2. A shape is drawn with a solid or dashed outline, and is left empty, given a faint fill or filled in. A dashed
	   outline is a part that is missing, and a faint fill is the step the problem is about.
	3. Problems about wording, and problems the schema finds, have no picture.
*/

export type FixShape = {
	shape: 'step' | 'decision' | 'dot';
	outline: 'solid' | 'dashed' | 'none';
	fill: 'none' | 'faint' | 'full';
};

export type FixPicture = {
	// The words a screen reader reads in place of the picture.
	description: string;
	before: [FixShape, FixShape];
	after: [FixShape, FixShape];
};

const problemStep: FixShape = { shape: 'step', outline: 'solid', fill: 'faint' };
const missingStep: FixShape = { shape: 'step', outline: 'dashed', fill: 'none' };
const fixedStep: FixShape = { shape: 'step', outline: 'solid', fill: 'none' };
const addedStep: FixShape = { shape: 'step', outline: 'none', fill: 'full' };
const filledDot: FixShape = { shape: 'dot', outline: 'none', fill: 'full' };

// The picture for each sort of problem that has one.
export const fixPictures: Partial<Record<JourneyProblemKind, FixPicture>> = {
	no_start: {
		description: 'Before: the start dot is not joined to a step. After: a line joins the start dot to the step.',
		before: [filledDot, problemStep],
		after: [filledDot, fixedStep]
	},
	no_next: {
		description: 'Before: the step has nothing after it. After: a line joins the step to an end.',
		before: [problemStep, { shape: 'dot', outline: 'dashed', fill: 'none' }],
		after: [fixedStep, filledDot]
	},
	not_joined: {
		description: 'Before: no step leads to this step. After: a line joins a step before it to this step.',
		before: [missingStep, problemStep],
		after: [addedStep, fixedStep]
	},
	way_out_leads_nowhere: {
		description: 'Before: a way out of the decision leads nowhere. After: a line joins that way out to a step.',
		before: [{ shape: 'decision', outline: 'solid', fill: 'faint' }, missingStep],
		after: [{ shape: 'decision', outline: 'solid', fill: 'none' }, addedStep]
	}
};
