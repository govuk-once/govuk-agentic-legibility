import { describe, expect, it } from 'vitest';
import { editedAgo } from '$lib/drafts/describe-draft';

const now = new Date('2026-11-25T12:00:00Z');

describe('how long ago a draft was edited', () => {
	it('says just now for less than a minute, and for a time ahead of the clock', () => {
		expect(editedAgo('2026-11-25T11:59:30Z', now)).toBe('edited just now');
		expect(editedAgo('2026-11-25T12:05:00Z', now)).toBe('edited just now');
	});

	it('gives the time in the largest unit it fills', () => {
		expect(editedAgo('2026-11-25T11:55:00Z', now)).toBe('edited 5 minutes ago');
		expect(editedAgo('2026-11-25T10:00:00Z', now)).toBe('edited 2 hours ago');
		expect(editedAgo('2026-11-22T12:00:00Z', now)).toBe('edited 3 days ago');
	});

	it('says yesterday and last week in place of one day or one week ago', () => {
		expect(editedAgo('2026-11-24T10:00:00Z', now)).toBe('edited yesterday');
		expect(editedAgo('2026-11-16T12:00:00Z', now)).toBe('edited last week');
	});
});
