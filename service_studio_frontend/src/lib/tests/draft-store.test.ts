import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { serviceExamples } from '$lib/examples/services';
import { createDraftStore } from '../draft-store';

// A stand in for the browser's session storage, so the tests run without a browser. It can be made to refuse.
function fakeStorage() {
	const items = new Map<string, string>();
	return {
		items,
		refuse: false,
		getItem(key: string) {
			return items.get(key) ?? null;
		},
		setItem(key: string, value: string) {
			if (this.refuse) throw new Error('Storage is blocked');
			items.set(key, value);
		}
	};
}

// A key of its own, so the tests check the store and not any one editor's key.
const { loadDraft, saveDraft } = createDraftStore('test-draft');

const example = serviceExamples.find((candidate) => candidate.slug === 'change_of_address')!.workflow!;

let storage: ReturnType<typeof fakeStorage>;
beforeEach(() => {
	storage = fakeStorage();
	vi.stubGlobal('sessionStorage', storage);
});
afterEach(() => vi.unstubAllGlobals());

describe('the held draft', () => {
	it('keeps drafts held under different keys apart', () => {
		const other = createDraftStore('other-draft');
		saveDraft(example);
		expect(other.loadDraft()).toEqual({ ok: false, reason: 'missing' });
		expect(loadDraft()).toEqual({ ok: true, workflow: example });
	});

	it('gives back the draft that was saved', () => {
		expect(saveDraft(example)).toBe(true);
		const loaded = loadDraft();
		expect(loaded).toEqual({ ok: true, workflow: example });
	});

	it('says there is no draft when nothing was saved', () => {
		expect(loadDraft()).toEqual({ ok: false, reason: 'missing' });
	});

	it('says the draft is invalid, and why, when what is stored is not JSON', () => {
		storage.items.set('test-draft', 'not json {');
		expect(loadDraft()).toEqual({ ok: false, reason: 'invalid', issues: [{ path: '(root)', message: 'The saved draft is not valid JSON.' }] });
	});

	it('checks the draft against the schema when it is loaded, so a changed one is refused', () => {
		saveDraft(example);
		const stored = JSON.parse(storage.items.get('test-draft')!);
		stored.manifest.schema = 'old';
		storage.items.set('test-draft', JSON.stringify(stored));

		const loaded = loadDraft();
		expect(loaded).toMatchObject({ ok: false, reason: 'invalid' });
		if (!loaded.ok && loaded.reason === 'invalid') expect(loaded.issues.map((issue) => issue.path)).toContain('manifest.schema');
	});

	it('returns false when the browser will not store it, and nothing is kept', () => {
		storage.refuse = true;
		expect(saveDraft(example)).toBe(false);
		expect(loadDraft()).toEqual({ ok: false, reason: 'missing' });
	});

	it('says there is no draft when the browser will not let storage be read', () => {
		vi.stubGlobal('sessionStorage', {
			getItem() {
				throw new Error('Blocked');
			}
		});
		expect(loadDraft()).toEqual({ ok: false, reason: 'missing' });
	});
});
