import { describe, expect, it } from 'vitest';
import { stateSchema } from '$lib/schema/workflow/process';
import { startLabel, stateLabels } from '../state-labels';

// Every kind of state in the schema, read from the schema itself so a new kind is noticed here.
const stateTypes = stateSchema.options.map((option) => option.shape.type.value);

describe('stateLabels', () => {
	it('has a label for every kind of state in the schema, and no others', () => {
		expect(Object.keys(stateLabels).sort()).toEqual([...stateTypes].sort());
	});

	it('uses the plain words for the two kinds that a person adds most', () => {
		expect(stateLabels.input).toBe('Question');
		expect(stateLabels.output).toBe('Message');
	});

	it('gives every kind a different, non empty label, so two kinds are never mistaken for each other', () => {
		const labels = Object.values(stateLabels);
		expect(labels.every((label) => label.trim().length > 0)).toBe(true);
		expect(new Set(labels).size).toBe(labels.length);
	});

	it('does not use all capitals, which the design rules forbid', () => {
		for (const label of [...Object.values(stateLabels), startLabel]) expect(label).not.toBe(label.toUpperCase());
	});
});
