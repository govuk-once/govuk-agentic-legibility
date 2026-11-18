import { describe, expect, it } from 'vitest';
import { publishedStages, stagesAt } from '../progress-stages';

describe('stagesAt', () => {
	it('marks the stages before the current one complete and the ones after it upcoming', () => {
		expect(stagesAt('Owner review').map((stage) => stage.state)).toEqual([
			'complete',
			'complete',
			'complete',
			'current',
			'upcoming',
			'upcoming'
		]);
	});
});

describe('publishedStages', () => {
	it('marks every stage complete', () => {
		expect(publishedStages.every((stage) => stage.state === 'complete')).toBe(true);
	});
});
