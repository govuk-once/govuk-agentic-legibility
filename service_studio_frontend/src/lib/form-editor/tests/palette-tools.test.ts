import { describe, expect, it } from 'vitest';
import { moduleCategories } from '$lib/modules/module-catalogue';
import { formPaletteTools } from '../palette-tools';

describe('formPaletteTools', () => {
	it('lets only the basic shapes be dragged: an input, a message, a decision, a start and an end', () => {
		expect(formPaletteTools.map((tool) => tool.module)).toEqual(['input', 'output', 'decision', 'start', 'end']);
	});

	it('names the kind of state an input or a message adds, and the draft shape for the rest', () => {
		expect(formPaletteTools.map((tool) => tool.value)).toEqual(['input', 'output', 'condition', 'start', 'end']);
	});

	it('gives every tool a different value, so a drop can tell them apart', () => {
		const values = formPaletteTools.map((tool) => tool.value);
		expect(new Set(values).size).toBe(values.length);
	});

	it('only names tiles that are in the module menu', () => {
		const keys = moduleCategories.flatMap((category) => category.modules.map((module) => module.key));
		for (const tool of formPaletteTools) expect(keys).toContain(tool.module);
	});
});
