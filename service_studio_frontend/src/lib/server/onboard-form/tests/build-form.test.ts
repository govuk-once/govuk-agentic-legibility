import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import { checkFormWorkflow } from '$lib/form-editor/schema/form-states';
import type { Process } from '$lib/schema/workflow/process';
import { parseWorkflow } from '$lib/schema/workflow/validate';
import { buildForm, formRunTimeout, statesNotForForms, withAnswerTypes, withFormatChecks, withModuleGroupIds } from '../build-form';

const details = { name: 'Register a trainer', description: 'Tell us who needs training.', links: ['https://www.gov.uk/a'] };

const finish = { state_type: 'end', status: 'success' };
const question = (schema: unknown, metadata?: Record<string, unknown>) => ({
	state_type: 'input',
	prompt: 'Q',
	schema,
	assign: 'answer',
	next: 'finish',
	...(metadata ? { metadata } : {})
});

// Builds a process as the model might write it. The cast is needed because each test gives only the keys it uses.
const generated = (states: Record<string, unknown>) =>
	({ process_id: 'main', version: '0.1.0', start: Object.keys(states)[0], vars: {}, states: { ...states, finish } }) as unknown as Process;

describe('statesNotForForms', () => {
	it('finds nothing in a form of questions, messages, decisions and ends', () => {
		const process = generated({
			say: { state_type: 'output', channel: 'transcript', message: 'Hello', next: 'ask' },
			ask: question({ kind: 'boolean' }),
			decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'answer' }, next: 'finish' }], default: 'finish' }
		});
		expect(statesNotForForms(process)).toEqual([]);
	});

	it('names each state a form cannot have, with where it is', () => {
		const process = generated({
			look_up: { state_type: 'api_call', method: 'GET', service: 's', url: '/u', next: 'pause' },
			pause: { state_type: 'wait', duration: 'PT1S', next: 'finish' }
		});
		expect(statesNotForForms(process)).toEqual([
			{ path: 'states.look_up.state_type', message: 'A form cannot have a state of type "api_call"' },
			{ path: 'states.pause.state_type', message: 'A form cannot have a state of type "wait"' }
		]);
	});
});

describe('withAnswerTypes', () => {
	it('keeps an answer type the model wrote that goes with the kind of answer', () => {
		const process = generated({ ask: question({ kind: 'string' }, { answer_type: 'email', description: 'Asks for an email.' }) });
		expect(withAnswerTypes(process)).toBe(process);
	});

	it('gives a question with no answer type the most general one for its kind, and keeps its other notes', () => {
		const process = generated({
			typed: question({ kind: 'string' }, { description: 'Kept.' }),
			yes_or_no: question({ kind: 'boolean' }),
			chosen: question({ kind: 'select_one', options: [{ value: 'a', label: 'A' }] }),
			uploaded: question({ kind: 'file_ref' })
		});
		const { states } = withAnswerTypes(process);
		expect(states.typed.metadata).toEqual({ description: 'Kept.', answer_type: 'text' });
		expect(states.yes_or_no.metadata).toEqual({ answer_type: 'selection' });
		expect(states.chosen.metadata).toEqual({ answer_type: 'selection' });
		expect(states.uploaded.metadata).toEqual({ answer_type: 'file' });
	});

	it('replaces an answer type that does not go with the kind of answer', () => {
		const process = generated({ ask: question({ kind: 'boolean' }, { answer_type: 'email' }), other: question({ kind: 'string' }, { answer_type: 'made_up' }) });
		const { states } = withAnswerTypes(process);
		expect(states.ask.metadata).toEqual({ answer_type: 'selection' });
		expect(states.other.metadata).toEqual({ answer_type: 'text' });
	});

	it('leaves states that are not questions alone, and does not change the process it was given', () => {
		const process = generated({ ask: question({ kind: 'string' }) });
		const before = JSON.stringify(process);
		expect(withAnswerTypes(process).states.finish).toBe(process.states.finish);
		expect(JSON.stringify(process)).toBe(before);
	});
});

describe('withFormatChecks', () => {
	it('gives a typed question whose answer type has a format the check of that format', () => {
		const process = withFormatChecks(generated({ ask: question({ kind: 'string' }, { answer_type: 'email' }) }));
		const ask = process.states.ask;
		expect(ask.state_type === 'input' && ask.schema).toMatchObject({ kind: 'string', normalise: 'lower_trim' });
		expect(ask.state_type === 'input' && ask.schema.kind === 'string' && ask.schema.pattern).toEqual(expect.any(String));
	});

	it('leaves a question whose answer type has no format, such as name, without a check', () => {
		const process = withFormatChecks(generated({ ask: question({ kind: 'string' }, { answer_type: 'name' }) }));
		expect(process.states.ask.state_type === 'input' && process.states.ask.schema).toEqual({ kind: 'string' });
	});
});

describe('withModuleGroupIds', () => {
	it('gives the states that shared a label one random code, and a different code to another label', () => {
		const process = withModuleGroupIds(
			generated({
				ask: question({ kind: 'boolean' }, { group: 'boolean_decision', group_id: 'accept_terms' }),
				decide: { state_type: 'choice', rules: [{ when: { op: 'is_true', path: 'answer' }, next: 'finish' }], default: 'finish', metadata: { group: 'boolean_decision', group_id: 'accept_terms' } },
				other: question({ kind: 'boolean' }, { group: 'boolean_decision', group_id: 'second' })
			})
		);
		const idOf = (code: string) => process.states[code].metadata?.group_id;
		expect(idOf('ask')).toBe(idOf('decide'));
		expect(idOf('ask')).not.toBe('accept_terms');
		expect(idOf('other')).not.toBe(idOf('ask'));
	});
});

describe('buildForm', () => {
	const form = buildForm(generated({ ask: question({ kind: 'string' }) }), details);

	it('gives a workflow that passes the schema checks and that the form editor can open', () => {
		const result = parseWorkflow(form);
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
		expect(checkFormWorkflow(form)).toEqual([]);
	});

	it('has no defaults for calls and the same run limit as the form examples', () => {
		expect(form.manifest.defaults).toEqual({});
		expect(form.manifest.executor.run_timeout).toBe(formRunTimeout);
		for (const example of formExamples) {
			expect(example.workflow?.manifest.defaults, example.slug).toEqual({});
			expect(example.workflow?.manifest.executor.run_timeout, example.slug).toBe(formRunTimeout);
		}
	});

	it('describes the manifest by the name of the form, as the form examples do, and keeps what it does in its notes', () => {
		expect(form.manifest.description).toBe('Register a trainer');
		expect(form.manifest.metadata).toEqual({ description: 'Tell us who needs training.' });
		expect(form.processes.register_a_trainer).not.toHaveProperty('metadata');
	});

	it('adds no notes to the manifest when the person did not say what the form does', () => {
		const undescribed = buildForm(generated({ ask: question({ kind: 'string' }) }), { ...details, description: '  ' });
		expect(undescribed.manifest).not.toHaveProperty('metadata');
	});

	it('gives the owner and the contact placeholders, and every question an answer type', () => {
		expect(form.manifest).toMatchObject({ owner: 'To be confirmed', contact: 'to.be.confirmed@example.com' });
		expect(form.processes.register_a_trainer.states.ask.metadata).toEqual({ answer_type: 'text' });
	});
});
