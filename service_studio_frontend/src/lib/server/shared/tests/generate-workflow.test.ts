import { describe, expect, it, vi } from 'vitest';
import type { Process } from '$lib/schema/workflow/process';
import { buildDraftWorkflow } from '$lib/server/shared/build-draft-workflow';
import { generateWorkflow, type DraftKind } from '$lib/server/shared/generate-workflow';
import { fakeModel } from '$lib/server/shared/tests/fake-model';

// Stands in for the real fetch, so no test reaches the internet.
vi.mock('$lib/server/shared/fetch-link', () => ({ fetchLinkText: async (url: string) => ({ url, text: 'Page words' }) }));

const details = { name: 'Report a change', description: 'Tell us what changed.', links: [] };

const reply = (states: Record<string, unknown>) => JSON.stringify({ process_id: 'main', version: '0.1.0', start: 'ask', vars: {}, states });
const finish = { state_type: 'end', status: 'success' };
const question = { state_type: 'input', prompt: 'What changed?', schema: { kind: 'string' }, assign: 'change', next: 'finish' };
const pause = { state_type: 'wait', duration: 'PT1S', next: 'finish' };

// A kind of draft that refuses a wait, so the check of its own can be seen working.
const kind: DraftKind = {
	subject: 'Thing',
	system: 'The instructions',
	wrap: (process: Process, given) => buildDraftWorkflow(process, given, { defaults: {}, runTimeout: 'P1D' }),
	checkProcess: (process) =>
		Object.entries(process.states).flatMap(([code, state]) => (state.state_type === 'wait' ? [{ path: `states.${code}`, message: 'No waiting' }] : []))
};

describe('generateWorkflow', () => {
	it('labels the name and description with the subject, and sends the instructions it was given', async () => {
		const { client, requests } = fakeModel([reply({ ask: question, finish })]);
		const result = await generateWorkflow(details, kind, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(requests[0].system).toBe('The instructions');
		expect(String(requests[0].messages[0].content)).toContain('Thing name: Report a change\n\nThing description: Tell us what changed.');
	});

	it('wraps the process the way the kind of draft says', async () => {
		const { client } = fakeModel([reply({ ask: question, finish })]);
		const result = await generateWorkflow(details, kind, { client, modelId: 'the-model' });

		if (!result.ok) throw new Error('expected a draft');
		expect(result.workflow.manifest.executor.run_timeout).toBe('P1D');
	});

	it('sends the problems its own check finds back to the model, and uses the corrected process', async () => {
		const { client, requests } = fakeModel([reply({ ask: pause, finish }), reply({ ask: question, finish })]);
		const result = await generateWorkflow(details, kind, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(requests).toHaveLength(2);
		expect(String(requests[1].messages[2].content)).toContain('states.ask: No waiting');
	});

	it('makes no check of its own when the kind of draft has none', async () => {
		const { client, requests } = fakeModel([reply({ ask: pause, finish })]);
		const { checkProcess: _none, ...unchecked } = kind;
		const result = await generateWorkflow(details, unchecked, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(requests).toHaveLength(1);
	});
});
