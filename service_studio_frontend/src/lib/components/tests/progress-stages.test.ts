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

	it('links only the complete stages that were given an address', () => {
		const links = { Start: '/start', Edit: '/edit', 'Owner review': '/owner', 'Tech review': '/tech' };
		expect(stagesAt('Owner review', links).map((stage) => stage.href)).toEqual(['/start', undefined, '/edit', undefined, undefined, undefined]);
	});

	it('links nothing when no addresses are given', () => {
		expect(stagesAt('Sign off').every((stage) => stage.href === undefined)).toBe(true);
	});
});

describe('publishedStages', () => {
	it('marks every stage complete', () => {
		expect(publishedStages.every((stage) => stage.state === 'complete')).toBe(true);
	});
});
