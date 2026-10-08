import { describe, expect, it } from 'vitest';
import { displayUrl, parseContextUrl } from './context';

describe('parseContextUrl', () => {
	it('accepts an https address and trims the spaces around it', () => {
		expect(parseContextUrl('  https://www.gov.uk/change-address  ')).toEqual({
			ok: true,
			url: 'https://www.gov.uk/change-address'
		});
	});

	it('asks for an address when the field is empty', () => {
		expect(parseContextUrl('   ')).toEqual({ ok: false, error: 'Enter a web address' });
	});

	it('rejects text that is not a web address', () => {
		const result = parseContextUrl('not a url');
		expect(result.ok).toBe(false);
	});

	it('rejects an address that is not http or https', () => {
		const result = parseContextUrl('ftp://example.com/file');
		expect(result).toEqual({ ok: false, error: 'Enter a web address that starts with https://' });
	});
});

describe('displayUrl', () => {
	it('drops the scheme, www and a trailing slash', () => {
		expect(displayUrl('https://www.gov.uk/change-address-driving-licence/')).toBe(
			'gov.uk/change-address-driving-licence'
		);
	});

	it('shows just the host for a bare address', () => {
		expect(displayUrl('https://www.gov.uk/')).toBe('gov.uk');
	});

	it('returns the text unchanged when it cannot be parsed', () => {
		expect(displayUrl('nonsense')).toBe('nonsense');
	});
});
