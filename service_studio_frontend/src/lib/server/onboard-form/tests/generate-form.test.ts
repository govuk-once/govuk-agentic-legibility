import { describe, expect, it, vi } from 'vitest';
import { fakeModel } from '$lib/server/shared/tests/fake-model';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import { generateForm } from '../generate-form';
import { FORM_SYSTEM_PROMPT } from '../system-prompt';

// Stands in for the real fetch, so no test reaches the internet.
vi.mock('$lib/server/shared/fetch-link', () => ({ fetchLinkText: async (url: string) => ({ url, text: 'Page words' }) }));

const details = { name: 'Register a trainer', description: 'Tell us who needs training.', links: ['https://www.gov.uk/a'] };

const reply = (states: Record<string, unknown>) => JSON.stringify({ process_id: 'main', version: '0.1.0', start: 'ask', vars: {}, states });
const finish = { state_type: 'end', status: 'success' };
const ask = { state_type: 'input', name: 'Email', prompt: 'Your email?', schema: { kind: 'string' }, assign: 'email', next: 'finish' };

describe('generateForm', () => {
	it('gives a draft form that passes the checks, wrapped as a form', async () => {
		const { client } = fakeModel([reply({ ask: { ...ask, metadata: { answer_type: 'email' } }, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		if (!result.ok) throw new Error(JSON.stringify(result.issues));
		expect(parseWorkflow(result.workflow).ok).toBe(true);
		expect(result.workflow.manifest).toMatchObject({ id: 'draft.register_a_trainer', defaults: {}, executor: { run_timeout: 'P7D' } });
		expect(result.workflow.processes.register_a_trainer.states.ask.metadata).toEqual({ answer_type: 'email' });
	});

	it('sends the form prompt, and labels the details as those of a form', async () => {
		const { client, requests } = fakeModel([reply({ ask, finish })]);
		await generateForm(details, { client, modelId: 'the-model' });

		expect(requests[0].system).toBe(FORM_SYSTEM_PROMPT);
		const brief = String(requests[0].messages[0].content);
		for (const part of ['Form name: Register a trainer', 'Form description: Tell us who needs training.', 'Page words']) {
			expect(brief).toContain(part);
		}
	});

	it('gives a question the model left without an answer type the most general one', async () => {
		const { client } = fakeModel([reply({ ask, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		if (!result.ok) throw new Error(JSON.stringify(result.issues));
		expect(result.workflow.processes.register_a_trainer.states.ask.metadata).toEqual({ answer_type: 'text' });
	});

	it('sends a state a form cannot have back to the model, and uses the corrected form', async () => {
		const call = { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'finish' };
		const { client, requests } = fakeModel([reply({ ask: call, finish }), reply({ ask, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(true);
		expect(requests).toHaveLength(2);
		expect(String(requests[1].messages[2].content)).toContain('A form cannot have a state of type "api_call"');
	});

	it('sends back a module the model gave the wrong states, and uses the corrected form', async () => {
		const marked = { group: 'boolean_decision', group_id: 'has_permit' };
		const decide = { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'answers.has_permit' }, next: 'finish' }], default: 'finish', metadata: marked };
		const typed = { ...ask, assign: 'answers.has_permit', next: 'decide', metadata: marked };
		const yesOrNo = { ...typed, schema: { kind: 'boolean' } };
		const { client, requests } = fakeModel([reply({ ask: typed, decide, finish }), reply({ ask: yesOrNo, decide, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		if (!result.ok) throw new Error(JSON.stringify(result.issues));
		expect(String(requests[1].messages[2].content)).toContain('must be made of: input with a boolean answer, choice');
		const { states } = result.workflow.processes.register_a_trainer;
		expect(states.ask.metadata?.group_id).toBe(states.decide.metadata?.group_id);
		expect(states.ask.metadata?.group_id).not.toBe('has_permit');
	});

	it('sends back a module a drafted form may not use, such as Submit', async () => {
		const { client, requests } = fakeModel([reply({ ask: { ...ask, metadata: { group: 'submit', group_id: 'send' } }, finish }), reply({ ask, finish })]);
		await generateForm(details, { client, modelId: 'the-model' });
		expect(String(requests[1].messages[2].content)).toContain('"submit" is not a module that can be used here');
	});

	it('gives a question the model gave a checked answer type the check of that format', async () => {
		const { client } = fakeModel([reply({ ask: { ...ask, metadata: { answer_type: 'email' } }, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		if (!result.ok) throw new Error(JSON.stringify(result.issues));
		const question = result.workflow.processes.register_a_trainer.states.ask;
		expect(question.state_type === 'input' && question.schema.kind === 'string' && question.schema.pattern).toEqual(expect.any(String));
	});

	it('returns the problems when the second try still has a state a form cannot have', async () => {
		const pause = { state_type: 'wait', duration: 'PT1S', next: 'finish' };
		const { client } = fakeModel([reply({ ask: pause, finish }), reply({ ask: pause, finish })]);
		const result = await generateForm(details, { client, modelId: 'the-model' });

		expect(result.ok).toBe(false);
		if (!result.ok) expect(result.issues).toEqual([{ path: 'states.ask.state_type', message: 'A form cannot have a state of type "wait"' }]);
	});
});
