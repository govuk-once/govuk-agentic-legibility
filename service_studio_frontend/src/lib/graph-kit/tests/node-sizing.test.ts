import { describe, expect, it } from 'vitest';
import { estimateStepNodeHeight, estimateStepNodeWidth } from '../node-sizing';

describe('estimateStepNodeWidth', () => {
	it('gives a short title the least width of a standard box', () => {
		expect(estimateStepNodeWidth('Pay')).toBe(260);
	});

	it('gives a longer title a wider box, up to the most a box may be', () => {
		expect(estimateStepNodeWidth('A title of thirty characters ok')).toBeGreaterThan(260);
		expect(estimateStepNodeWidth('x'.repeat(200))).toBe(420);
	});

	it('gives a compact box a smaller least width, so a short title makes a narrower box', () => {
		expect(estimateStepNodeWidth('Pay', 'compact')).toBe(200);
		expect(estimateStepNodeWidth('x'.repeat(200), 'compact')).toBe(420);
	});
});

describe('estimateStepNodeHeight', () => {
	it('gives a title of one line the least height of a standard box', () => {
		expect(estimateStepNodeHeight('Pay', 260)).toBe(56);
	});

	it('gives a title that wraps a taller box, and grows for each extra line under the title', () => {
		const wrapped = estimateStepNodeHeight('x'.repeat(60), 260);
		expect(wrapped).toBeGreaterThan(56);
		expect(estimateStepNodeHeight('Pay', 260, 1)).toBeGreaterThan(estimateStepNodeHeight('Pay', 260));
	});

	it('gives a compact box less height than a standard box with the same title', () => {
		expect(estimateStepNodeHeight('Pay', 200, 0, 'compact')).toBe(40);
		expect(estimateStepNodeHeight('x'.repeat(60), 260, 0, 'compact')).toBeLessThan(estimateStepNodeHeight('x'.repeat(60), 260));
	});
});
