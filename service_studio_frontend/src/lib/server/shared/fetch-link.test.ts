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

	describe('the list of sites the assistant may read', () => {
		const redirect = (to: string, status = 302) => new Response(null, { status, headers: { location: to } });
		const page = (words: string) => new Response(`<p>${words}</p>`, { status: 200 });

		it.each(['https://example.com/page', 'http://localhost:3000', 'http://169.254.169.254/latest/meta-data', 'mailto:team@gov.uk'])(
			'refuses %s without making any request',
			async (url) => {
				const fetchMock = vi.fn();
				vi.stubGlobal('fetch', fetchMock);

				const result = await fetchLinkText(url);

				expect(result).toEqual({ url, error: 'That site is not on the list of sites the assistant can read' });
				expect(fetchMock).not.toHaveBeenCalled();
			}
		);

		it('tells the fetch not to follow redirects itself, so that every stop can be checked', async () => {
			const fetchMock = vi.fn().mockResolvedValue(page('Hello'));
			vi.stubGlobal('fetch', fetchMock);

			await fetchLinkText('https://www.gov.uk/a');

			expect(fetchMock.mock.calls[0][1]).toMatchObject({ redirect: 'manual' });
		});

		it('follows a redirect that stays on the list, including one with a relative address', async () => {
			const fetchMock = vi
				.fn()
				.mockResolvedValueOnce(redirect('https://assets.publishing.service.gov.uk/moved'))
				.mockResolvedValueOnce(redirect('/moved-again', 301))
				.mockResolvedValueOnce(page('Final words'));
			vi.stubGlobal('fetch', fetchMock);

			const result = await fetchLinkText('https://www.gov.uk/old');

			expect(result).toEqual({ url: 'https://www.gov.uk/old', text: 'Final words' });
			expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
				'https://www.gov.uk/old',
				'https://assets.publishing.service.gov.uk/moved',
				'https://assets.publishing.service.gov.uk/moved-again'
			]);
		});

		it.each(['https://example.com/elsewhere', 'http://localhost:3000/admin', 'http://169.254.169.254/latest/meta-data'])(
			'stops at a redirect to %s and does not fetch it',
			async (to) => {
				const fetchMock = vi.fn().mockResolvedValueOnce(redirect(to));
				vi.stubGlobal('fetch', fetchMock);

				const result = await fetchLinkText('https://www.gov.uk/a');

				expect(result).toEqual({
					url: 'https://www.gov.uk/a',
					error: 'The link redirects to a site that is not on the list of sites the assistant can read'
				});
				expect(fetchMock).toHaveBeenCalledTimes(1);
			}
		);

		it('gives up on a link that redirects too many times', async () => {
			const fetchMock = vi.fn().mockImplementation(async () => redirect('https://www.gov.uk/again'));
			vi.stubGlobal('fetch', fetchMock);

			const result = await fetchLinkText('https://www.gov.uk/loop');

			expect(result).toEqual({ url: 'https://www.gov.uk/loop', error: 'The link redirects too many times' });
			expect(fetchMock).toHaveBeenCalledTimes(6);
		});

		it('treats a redirect with no address as the answer, not as something to follow', async () => {
			vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 302 })));

			const result = await fetchLinkText('https://www.gov.uk/a');

			expect(result).toEqual({ url: 'https://www.gov.uk/a', error: 'Responded with status 302' });
		});
	});
});
