import { describe, expect, it } from 'vitest';
import { stateUnionSchema } from '$lib/schema/workflow/process';
import { answerDefinitionSchema } from '$lib/schema/workflow/input-state';
import { answerKindLabels, startLabel, stateLabels, stateOutlineColours, stateTagColours } from '../state-labels';

// Every kind of state in the schema, read from the schema itself so a new kind is noticed here.
const stateTypes = stateUnionSchema.options.map((option) => option.shape.state_type.value);

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

describe('stateTagColours', () => {
	it('has a colour for every kind of state in the schema, and no others', () => {
		expect(Object.keys(stateTagColours).sort()).toEqual([...stateTypes].sort());
	});

	it('uses the colours chosen for questions, messages, decisions and assign states', () => {
		expect(stateTagColours.input).toBe('blue');
		expect(stateTagColours.output).toBe('purple');
		expect(stateTagColours.choice).toBe('yellow');
		expect(stateTagColours.assign).toBe('grey');
	});
});

describe('stateOutlineColours', () => {
	it('gives a question box and a message box an outline colour, and no other kind of state', () => {
		expect(Object.keys(stateOutlineColours).sort()).toEqual(['input', 'output']);
	});

	it('gives the two boxes different colours, each written as a CSS colour', () => {
		expect(stateOutlineColours.input).not.toBe(stateOutlineColours.output);
		for (const colour of Object.values(stateOutlineColours)) expect(colour).toMatch(/^#[0-9a-f]{6}$/);
	});
});

describe('answerKindLabels', () => {
	// Every kind of answer in the schema, read from the schema itself so a new kind is noticed here.
	const answerKinds = answerDefinitionSchema.options.flatMap((option) => {
		const kind = option.shape.kind;
		return 'options' in kind ? kind.options : [kind.value];
	});

	it('has a label for every kind of answer in the schema, and no others', () => {
		expect(Object.keys(answerKindLabels).sort()).toEqual([...answerKinds].sort());
	});

	it('uses plain words, each different from the others', () => {
		expect(answerKindLabels.string).toBe('Text');
		expect(answerKindLabels.boolean).toBe('Yes or no');
		expect(answerKindLabels.select_one).toBe('Choose one');
		expect(new Set(Object.values(answerKindLabels)).size).toBe(Object.keys(answerKindLabels).length);
	});
});
