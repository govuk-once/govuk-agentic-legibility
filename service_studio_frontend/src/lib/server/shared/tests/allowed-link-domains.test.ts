import { describe, expect, it } from 'vitest';
import { allowedLinkDomains, isAllowedLink } from '../allowed-link-domains';

describe('allowedLinkDomains', () => {
	it('starts with gov.uk only', () => {
		expect(allowedLinkDomains).toEqual(['gov.uk']);
	});
});

describe('isAllowedLink', () => {
	it.each([
		'https://gov.uk',
		'https://www.gov.uk/change-address-driving-licence',
		'https://assets.publishing.service.gov.uk/media/abc.pdf',
		'http://www.gov.uk/page?a=1#top',
		'HTTPS://WWW.GOV.UK/PAGE'
	])('accepts %s', (link) => {
		expect(isAllowedLink(link)).toBe(true);
	});

	it.each([
		'https://example.com/page',
		'https://nhs.uk/conditions',
		'https://evilgov.uk',
		'https://gov.uk.example.com',
		'https://example.com/gov.uk',
		'https://example.com?next=https://www.gov.uk',
		'https://www.gov.uk@example.com/page',
		'https://www.gov.uk./page'
	])('refuses %s, because its host is not gov.uk or a subdomain of it', (link) => {
		expect(isAllowedLink(link)).toBe(false);
	});

	it.each(['http://localhost:3000', 'http://127.0.0.1', 'http://[::1]/', 'http://192.168.1.5/admin', 'http://169.254.169.254/latest/meta-data'])(
		'refuses %s, an address that only the server can reach',
		(link) => {
			expect(isAllowedLink(link)).toBe(false);
		}
	);

	it.each(['ftp://www.gov.uk/file', 'mailto:team@gov.uk', 'file:///etc/passwd', 'javascript:alert(1)', 'gov.uk', 'www.gov.uk/page', ''])(
		'refuses %s, because it is not a web address',
		(link) => {
			expect(isAllowedLink(link)).toBe(false);
		}
	);

	it('refuses a link with a user name, a password or a port that is not the usual one', () => {
		expect(isAllowedLink('https://user:pass@www.gov.uk/page')).toBe(false);
		expect(isAllowedLink('https://www.gov.uk:8443/page')).toBe(false);
	});

	it('uses the domains it is given in place of the list, so a test can have a list of its own', () => {
		expect(isAllowedLink('https://www.example.org/a', ['example.org'])).toBe(true);
		expect(isAllowedLink('https://www.gov.uk/a', ['example.org'])).toBe(false);
	});
});
