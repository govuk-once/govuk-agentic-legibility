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

	it('shows an earlier stage that is named as unfinished as not finished', () => {
		const stages = stagesAt('Sign off', ['Tech review']);
		expect(stages[4]).toEqual({ number: 5, label: 'Tech review not finished', state: 'unfinished' });
		expect(stages[5]).toEqual({ number: 6, label: 'Sign off', state: 'current' });
	});

	it('ignores a stage named as unfinished that comes after the current one', () => {
		expect(stagesAt('Edit', ['Sign off'])[5].state).toBe('upcoming');
	});
});

describe('publishedStages', () => {
	it('marks every stage complete', () => {
		expect(publishedStages.every((stage) => stage.state === 'complete')).toBe(true);
	});
});
