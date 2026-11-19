import { describe, expect, it } from 'vitest';
import { formPaletteTools } from '../palette-tools';
import { stateLabels } from '../state-labels';

describe('formPaletteTools', () => {
	it('offers a question, a message, a decision, a start and an end, in that order', () => {
		expect(formPaletteTools.map((tool) => tool.label)).toEqual(['Question', 'Message', 'Decision', 'Start', 'End']);
	});

	it('takes the words for a state from the same place as the tags on the cards', () => {
		const byValue = Object.fromEntries(formPaletteTools.map((tool) => [tool.value, tool.label]));
		expect(byValue.input).toBe(stateLabels.input);
		expect(byValue.output).toBe(stateLabels.output);
		expect(byValue.condition).toBe(stateLabels.choice);
		expect(byValue.end).toBe(stateLabels.end);
	});

	it('names the kind of state a question or a message adds, and the draft shape for the rest', () => {
		expect(formPaletteTools.map((tool) => tool.value)).toEqual(['input', 'output', 'condition', 'start', 'end']);
	});

	it('gives every shape a different value, so a drop can tell them apart', () => {
		const values = formPaletteTools.map((tool) => tool.value);
		expect(new Set(values).size).toBe(values.length);
	});

	it('draws a question and a message as boxes, a decision as a diamond and a start and an end as dots', () => {
		expect(formPaletteTools.map((tool) => tool.shape)).toEqual(['step', 'step', 'condition', 'start', 'end']);
	});
});
