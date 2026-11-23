import { describe, expect, it } from 'vitest';
import { moduleCategories } from '$lib/modules/module-catalogue';
import { moduleDefinitions } from '$lib/modules/module-states';
import { formPaletteTools } from '../palette-tools';

describe('formPaletteTools', () => {
	it('lets the basic shapes be dragged: an input, a message, a decision, a start and an end', () => {
		expect(formPaletteTools.slice(0, 5).map((tool) => tool.module)).toEqual(['input', 'output', 'decision', 'start', 'end']);
	});

	it('names the kind of state an input or a message adds, and the draft shape for the other basic shapes', () => {
		expect(formPaletteTools.slice(0, 5).map((tool) => tool.value)).toEqual(['input', 'output', 'condition', 'start', 'end']);
	});

	it('lets every module that adds states be dragged, found by its key', () => {
		const modules = formPaletteTools.filter((tool) => tool.shape === 'module');
		expect(modules.map((tool) => tool.value).sort()).toEqual(Object.keys(moduleDefinitions).sort());
		for (const tool of modules) expect(tool.value).toBe(tool.module);
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
