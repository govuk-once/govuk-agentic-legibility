import type { PaletteTool } from '$lib/modules/module-catalogue';

/*
	What the form editor lets the person drag from the module menu onto the canvas: the basic shapes. Input and Message
	add a single question or message, and the decision, start and end place shapes that stay drafts until they are
	joined to the process. The modules are shown but cannot be dragged until they add their own states.
*/
export const formPaletteTools: PaletteTool[] = [
	{ module: 'input', value: 'input', shape: 'step' },
	{ module: 'output', value: 'output', shape: 'step' },
	{ module: 'decision', value: 'condition', shape: 'condition' },
	{ module: 'start', value: 'start', shape: 'start' },
	{ module: 'end', value: 'end', shape: 'end' }
];
