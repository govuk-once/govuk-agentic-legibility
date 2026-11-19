import { describe, expect, it, vi } from 'vitest';
import { readLinks } from '../read-links';

// Stands in for the real fetch, so no test reaches the internet. Each address answers as the test says.
const fetched = vi.hoisted(() => ({ asked: [] as string[] }));
vi.mock('../fetch-link', () => ({
	fetchLinkText: async (url: string) => {
		fetched.asked.push(url);
		return url.includes('bad') ? { url, error: 'Responded with status 404' } : { url, text: `Words from ${url}` };
	}
}));

describe('readLinks', () => {
	it('turns each page that could be read into a section naming its address', async () => {
		const result = await readLinks(['https://a.gov.uk', 'https://b.gov.uk']);
		expect(result.sections).toEqual(['Source: https://a.gov.uk\nWords from https://a.gov.uk', 'Source: https://b.gov.uk\nWords from https://b.gov.uk']);
		expect(result.warnings).toEqual([]);
	});

	it('leaves out a link that could not be read and says which one and why, while keeping the others', async () => {
		const result = await readLinks(['https://a.gov.uk', 'https://bad.gov.uk']);
		expect(result.sections).toHaveLength(1);
		expect(result.warnings).toEqual(['Could not read https://bad.gov.uk: Responded with status 404']);
	});

	it('skips empty links without trying to read them', async () => {
		fetched.asked = [];
		await readLinks(['', 'https://a.gov.uk', '']);
		expect(fetched.asked).toEqual(['https://a.gov.uk']);
	});

	it('gives nothing back when there are no links', async () => {
		expect(await readLinks([])).toEqual({ sections: [], warnings: [] });
	});
});
