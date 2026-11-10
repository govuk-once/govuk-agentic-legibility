import { describe, expect, it } from 'vitest';
import { versionSchema } from '$lib/schema/workflow/primitives';
import { firstVersion, isWebAddress, slugOf } from '../onboard-details';

describe('slugOf', () => {
	it('turns a name into lower case words joined by underscores', () => {
		expect(slugOf('Change driving licence address')).toBe('change_driving_licence_address');
		expect(slugOf('  Apply: for a (new) licence!  ')).toBe('apply_for_a_new_licence');
	});

	it('gives a name with nothing usable in it a name of its own', () => {
		expect(slugOf('')).toBe('untitled');
		expect(slugOf('!!!')).toBe('untitled');
	});
});

describe('firstVersion', () => {
	it('is a version that the schema accepts, because a first draft is given it', () => {
		expect(versionSchema.safeParse(firstVersion).success).toBe(true);
	});
});

describe('isWebAddress', () => {
	it.each([
		'https://www.gov.uk/change-address-driving-licence',
		'http://example.com/page?a=1#top',
		'HTTPS://WWW.GOV.UK'
	])('accepts %s', (link) => {
		expect(isWebAddress(link)).toBe(true);
	});

	it.each(['', 'gov.uk', 'www.gov.uk/page', 'not a link'])('refuses "%s", because it is not a URL', (link) => {
		expect(isWebAddress(link)).toBe(false);
	});

	it.each(['ftp://files.example.com/a', 'mailto:someone@example.com', 'file:///etc/passwd', 'javascript:alert(1)', 'data:text/plain,hi'])(
		'refuses %s, because it does not use http or https',
		(link) => {
			expect(isWebAddress(link)).toBe(false);
		}
	);
});
