import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import { deleteDraft, listDrafts, openDraft, readOpenDraft, saveDraft, setOpenDraft } from '../draft-store';

// A stand in for the browser's local and session storage, so the tests run without a browser. It can be made to
// refuse to store anything.
function fakeStorage() {
	const items = new Map<string, string>();
	return {
		items,
		refuse: false,
		get length() {
			return items.size;
		},
		key(index: number) {
			return Array.from(items.keys())[index] ?? null;
		},
		getItem(key: string) {
			return items.get(key) ?? null;
		},
		setItem(key: string, value: string) {
			if (this.refuse) throw new Error('Storage is blocked');
			items.set(key, value);
		},
		removeItem(key: string) {
			items.delete(key);
		}
	};
}

const workflow = serviceExamples.find((candidate) => candidate.slug === 'change_of_address')!.workflow!;

const firstDraft = { id: 'first', name: 'Change of address', stage: 'Edit' as const, workflow, positions: { start: { x: 10, y: 20 } } };

let local: ReturnType<typeof fakeStorage>;
let session: ReturnType<typeof fakeStorage>;
beforeEach(() => {
	local = fakeStorage();
	session = fakeStorage();
	vi.stubGlobal('localStorage', local);
	vi.stubGlobal('sessionStorage', session);
});
afterEach(() => {
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('saving and opening a draft', () => {
	it('gives back the draft that was saved, with the time it was saved', async () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-11-24T10:00:00Z'));

		const saved = await saveDraft(firstDraft);
		expect(saved.savedAt).toBe('2026-11-24T10:00:00.000Z');
		expect(await openDraft('first')).toEqual({ ok: true, draft: saved });
	});

	it('replaces the draft with the same id', async () => {
		await saveDraft(firstDraft);
		await saveDraft({ ...firstDraft, stage: 'Owner review' });

		const opened = await openDraft('first');
		expect(opened.ok && opened.draft.stage).toBe('Owner review');
		expect(await listDrafts()).toHaveLength(1);
	});

	it('keeps only the manifest and processes of the form', async () => {
		const withExtra = { ...workflow, extra: 'not kept' };
		const saved = await saveDraft({ ...firstDraft, workflow: withExtra });
		expect(Object.keys(saved.workflow)).toEqual(['manifest', 'processes']);
	});

	it('is rejected when the browser will not store it', async () => {
		local.refuse = true;
		await expect(saveDraft(firstDraft)).rejects.toThrow();
		expect(await openDraft('first')).toEqual({ ok: false, reason: 'missing' });
	});

	it('says a draft is missing when nothing was saved with that id', async () => {
		expect(await openDraft('nothing')).toEqual({ ok: false, reason: 'missing' });
	});

	it('says a draft cannot be read when what is stored is not JSON', async () => {
		local.items.set('service-studio.draft.first', 'not json {');
		expect(await openDraft('first')).toEqual({ ok: false, reason: 'unreadable' });
	});

	it('says a draft cannot be read when what is stored is not shaped like a draft', async () => {
		local.items.set('service-studio.draft.first', JSON.stringify({ id: 'first', stage: 'Somewhere else' }));
		expect(await openDraft('first')).toEqual({ ok: false, reason: 'unreadable' });
	});

	it('says a draft cannot be read when the process its manifest starts at is not in it', async () => {
		const saved = await saveDraft(firstDraft);
		const withoutEntry = { ...saved, workflow: { ...saved.workflow, processes: {} } };
		local.items.set('service-studio.draft.first', JSON.stringify(withoutEntry));
		expect(await openDraft('first')).toEqual({ ok: false, reason: 'unreadable' });
	});
});

describe('the list of drafts', () => {
	it('lists each draft without its form, the most recently saved first', async () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-11-24T10:00:00Z'));
		await saveDraft(firstDraft);
		vi.setSystemTime(new Date('2026-11-24T11:00:00Z'));
		await saveDraft({ ...firstDraft, id: 'second', name: 'Trainer information', stage: 'Tech review' });

		expect(await listDrafts()).toEqual([
			{ id: 'second', name: 'Trainer information', stage: 'Tech review', savedAt: '2026-11-24T11:00:00.000Z' },
			{ id: 'first', name: 'Change of address', stage: 'Edit', savedAt: '2026-11-24T10:00:00.000Z' }
		]);
	});

	it('leaves out anything else the site stores and drafts that cannot be read', async () => {
		await saveDraft(firstDraft);
		local.items.set('service-studio.something-else', '{}');
		local.items.set('service-studio.draft.broken', 'not json {');

		expect((await listDrafts()).map((draft) => draft.id)).toEqual(['first']);
	});

	it('is empty when there are no drafts', async () => {
		expect(await listDrafts()).toEqual([]);
	});
});

describe('deleting a draft', () => {
	it('removes the draft so it can no longer be opened or listed', async () => {
		await saveDraft(firstDraft);
		await deleteDraft('first');

		expect(await openDraft('first')).toEqual({ ok: false, reason: 'missing' });
		expect(await listDrafts()).toEqual([]);
	});

	it('does nothing when there is no draft with that id', async () => {
		await expect(deleteDraft('nothing')).resolves.toBeUndefined();
	});
});

describe('the draft open in this tab', () => {
	it('gives back the id that was set', () => {
		setOpenDraft('first');
		expect(readOpenDraft()).toBe('first');
	});

	it('gives nothing when no draft has been opened in this tab', () => {
		expect(readOpenDraft()).toBeUndefined();
	});

	it('is kept in the tab and not with the drafts', () => {
		setOpenDraft('first');
		expect(session.items.get('service-studio.open-draft')).toBe('first');
		expect(local.items.size).toBe(0);
	});
});
