import { describe, expect, it } from 'vitest';
import { basicCategories, moduleCategories, moduleTileFor } from '$lib/modules/module-catalogue';

const modules = moduleCategories.flatMap((category) => category.modules);

describe('moduleCategories', () => {
	it('lists the categories in the order of the design', () => {
		expect(moduleCategories.map((category) => category.label)).toEqual([
			'Feedback',
			'Ask',
			'Decisions',
			'Time',
			'Flex connections',
			'Offline',
			'Basics'
		]);
	});

	it('gives every module a different key, so the group saved on its states can be traced back to it', () => {
		const keys = modules.map((module) => module.key);
		expect(new Set(keys).size).toBe(keys.length);
	});

	it('writes every key in lower case with underscores, so it is safe to save in metadata', () => {
		for (const module of modules) expect(module.key).toMatch(/^[a-z]+(_[a-z]+)*$/);
	});

	it('gives every module a name and a line saying what it does, for its tooltip', () => {
		for (const module of modules) {
			expect(module.label).not.toBe('');
			expect(module.description).not.toBe('');
		}
	});
});

describe('basicCategories', () => {
	it('holds only the basic shapes', () => {
		expect(basicCategories.flatMap((category) => category.modules.map((module) => module.key))).toEqual(['start', 'input', 'output', 'decision', 'end']);
	});
});

describe('moduleTileFor', () => {
	it('finds the tile of a module by its key, and nothing for a key that is not in the menu', () => {
		expect(moduleTileFor('boolean_decision')?.label).toBe('Yes / No');
		expect(moduleTileFor('not_a_module')).toBeUndefined();
	});
});
