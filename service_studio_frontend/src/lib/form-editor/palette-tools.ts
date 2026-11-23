import type { PaletteTool } from '$lib/modules/module-catalogue';
import { moduleDefinitions, type ModuleKey } from '$lib/modules/module-states';

/*
	What the form editor lets the person drag from the module menu onto the canvas. Input and Message add a single
	input or message, and the decision, start and end place shapes that stay drafts until they are joined to the
	process. Every module adds its own states, and is found by its key.
*/
export const formPaletteTools: PaletteTool[] = [
	{ module: 'input', value: 'input', shape: 'step' },
	{ module: 'output', value: 'output', shape: 'step' },
	{ module: 'decision', value: 'condition', shape: 'condition' },
	{ module: 'start', value: 'start', shape: 'start' },
	{ module: 'end', value: 'end', shape: 'end' },
	...(Object.keys(moduleDefinitions) as ModuleKey[]).map((key): PaletteTool => ({ module: key, value: key, shape: 'module' }))
];
