import type { PaletteTool } from '$lib/graph-kit/NodePalette.svelte';
import { stateLabels, startLabel } from './state-labels';

/*
	The shapes the form editor offers on its palette. A form is made of questions and messages, joined by decisions,
	between a start and an end. The value of a question or a message is the kind of state it adds, input or output,
	so the canvas can add a state of that kind when the shape is dropped. The value of a decision, a start and an end is
	the name the canvas uses for a shape that stays a draft until it is joined to the process.
*/
export const formPaletteTools: PaletteTool[] = [
	{ value: 'input', label: stateLabels.input, shape: 'step' },
	{ value: 'output', label: stateLabels.output, shape: 'step' },
	{ value: 'condition', label: stateLabels.choice, shape: 'condition' },
	{ value: 'start', label: startLabel, shape: 'start' },
	{ value: 'end', label: stateLabels.end, shape: 'end' }
];
