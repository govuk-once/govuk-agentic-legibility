import { describe, expect, it } from 'vitest';
import { durationAsAmount, durationFrom, durationInSeconds } from '$lib/schema/workflow/durations';

describe('durationInSeconds', () => {
	it('counts weeks, days, hours, minutes and seconds', () => {
		expect(durationInSeconds('PT30S')).toBe(30);
		expect(durationInSeconds('PT30M')).toBe(1800);
		expect(durationInSeconds('P1DT2H')).toBe(93600);
		expect(durationInSeconds('P1W')).toBe(604800);
	});

	it('gives nothing for years, months or text that is not a duration', () => {
		expect(durationInSeconds('P1Y')).toBeUndefined();
		expect(durationInSeconds('P1M')).toBeUndefined();
		expect(durationInSeconds('seven days')).toBeUndefined();
	});
});

describe('durationAsAmount', () => {
	it('uses the largest unit the duration divides into exactly', () => {
		expect(durationAsAmount('P7D')).toEqual({ amount: 7, unit: 'days' });
		expect(durationAsAmount('PT90M')).toEqual({ amount: 90, unit: 'minutes' });
		expect(durationAsAmount('P1DT12H')).toEqual({ amount: 36, unit: 'hours' });
	});
});

describe('durationFrom', () => {
	it('writes a number of one unit as a duration that reads back the same', () => {
		expect(durationFrom(7, 'days')).toBe('P7D');
		expect(durationFrom(12, 'hours')).toBe('PT12H');
		expect(durationFrom(30, 'minutes')).toBe('PT30M');
		expect(durationFrom(5, 'seconds')).toBe('PT5S');
		expect(durationAsAmount(durationFrom(90, 'minutes'))).toEqual({ amount: 90, unit: 'minutes' });
	});
});
