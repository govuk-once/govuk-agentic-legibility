import { describe, expect, it } from 'vitest';
import type { WaitState } from '$lib/schema/workflow/states';
import { typedDurationInWords, waitDurationText, waitWithDuration } from '../wait-values';

const wait: WaitState = { state_type: 'wait', name: 'Wait', duration: 'PT30M', next: 'check' };

describe('waitDurationText', () => {
	it('writes a duration as it is and a saved value by its name', () => {
		expect(waitDurationText(wait)).toBe('PT30M');
		expect(waitDurationText({ ...wait, duration: { $: 'wait_time' } })).toBe('wait_time');
	});
});

describe('waitWithDuration', () => {
	it('reads a duration as a duration and a name as a saved value', () => {
		expect(waitWithDuration(wait, ' PT1H ')).toEqual({ ok: true, state: { ...wait, duration: 'PT1H' } });
		expect(waitWithDuration(wait, 'wait_time')).toEqual({ ok: true, state: { ...wait, duration: { $: 'wait_time' } } });
	});

	it('refuses text that is neither', () => {
		expect(waitWithDuration(wait, '30 minutes').ok).toBe(false);
		expect(waitWithDuration(wait, '').ok).toBe(false);
	});
});

describe('typedDurationInWords', () => {
	it('says how long a typed duration is, and nothing for a name', () => {
		expect(typedDurationInWords('PT30M')).toBe('30 minutes');
		expect(typedDurationInWords('wait_time')).toBeUndefined();
	});
});
