import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchLinkText } from './fetch-link';

describe('fetchLinkText', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('strips scripts, styles and tags, and collapses whitespace', async () => {
		const html = `
			<html>
				<head><style>body { color: red; }</style></head>
				<body>
					<script>console.log('tracking');</script>
					<nav>Home</nav>
					<p>Apply   for a   licence.</p>
				</body>
			</html>
		`;
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(new Response(html, { status: 200 }))
		);

		const result = await fetchLinkText('https://example.gov.uk/apply');

		expect(result).toEqual({
			url: 'https://example.gov.uk/apply',
			text: 'Home Apply for a licence.'
		});
	});

	it('truncates very long pages to the character budget', async () => {
		const html = `<p>${'a'.repeat(30000)}</p>`;
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(html, { status: 200 })));

		const result = await fetchLinkText('https://example.gov.uk/long-page');

		expect('text' in result && result.text.length).toBe(20000);
	});

	it('reports a non 200 response as an error rather than throwing', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })));

		const result = await fetchLinkText('https://example.gov.uk/missing');

		expect(result).toEqual({ url: 'https://example.gov.uk/missing', error: 'Responded with status 404' });
	});

	it('reports a network failure as an error rather than throwing', async () => {
		vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));

		const result = await fetchLinkText('https://example.gov.uk/unreachable');

		expect(result).toEqual({ url: 'https://example.gov.uk/unreachable', error: 'network down' });
	});
});
