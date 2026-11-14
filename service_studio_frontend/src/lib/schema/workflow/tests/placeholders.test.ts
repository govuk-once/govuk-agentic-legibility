import { describe, expect, it } from 'vitest';
import { exampleWorkflows } from './example-states';
import {
	defaultEndStatus,
	isUndecidedRule,
	isUnconnectedApiCall,
	placeholderInput,
	placeholderMessage,
	placeholderOutput,
	placeholderOwner,
	placeholderQuestion,
	undecidedRule,
	unconnectedApiCallDetails
} from '../placeholders';
import { parseProcess, parseWorkflow } from '../validate';

describe('placeholders pass validation', () => {
	// A process that uses every placeholder: an unconnected call, then a decision with the
	// undecided rule, then an end with the default status.
	const process = {
		process_id: 'draft',
		version: '0.1.0',
		start: 'look_up',
		vars: {},
		states: {
			look_up: { state_type: 'api_call', ...unconnectedApiCallDetails, next: 'decide' },
			decide: { state_type: 'choice', rules: [{ when: undecidedRule, next: 'finish' }], default: 'finish' },
			finish: { state_type: 'end', status: defaultEndStatus }
		}
	};

	it('accepts a process built from the placeholders', () => {
		const result = parseProcess(process);
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});

	it('accepts a workflow whose owner and contact are the placeholders', () => {
		const example = exampleWorkflows()[0];
		const manifest = { ...(example.manifest as object), ...placeholderOwner };
		const result = parseWorkflow({ manifest, processes: example.processes });
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});
});

describe('placeholderInput and placeholderOutput', () => {
	it('gives a question the placeholder wording, a text answer and a variable named after the state', () => {
		expect(placeholderInput('new_step')).toEqual({ prompt: placeholderQuestion, schema: { kind: 'string' }, assign: 'answer_new_step' });
	});

	it('keeps a question that is given and uses the placeholder for an empty one', () => {
		expect(placeholderInput('a', 'Is it right?').prompt).toBe('Is it right?');
		expect(placeholderInput('a', '').prompt).toBe(placeholderQuestion);
	});

	it('names the variable from a code that holds characters a variable cannot', () => {
		expect(placeholderInput('say hello-now').assign).toBe('answer_say_hello_now');
	});

	it('gives a message the placeholder wording in the transcript, and keeps a message that is given', () => {
		expect(placeholderOutput()).toEqual({ channel: 'transcript', message: placeholderMessage });
		expect(placeholderOutput('Thank you.')).toEqual({ channel: 'transcript', message: 'Thank you.' });
	});

	it('makes states that pass the process checks', () => {
		const process = {
			process_id: 'draft',
			version: '0.1.0',
			start: 'ask',
			vars: {},
			states: {
				ask: { state_type: 'input', ...placeholderInput('ask'), next: 'say' },
				say: { state_type: 'output', ...placeholderOutput(), next: 'finish' },
				finish: { state_type: 'end', status: defaultEndStatus }
			}
		};
		const result = parseProcess(process);
		expect(result.ok, JSON.stringify(!result.ok && result.issues)).toBe(true);
	});
});

describe('isUnconnectedApiCall', () => {
	it('recognises a call with the placeholder details', () => {
		expect(isUnconnectedApiCall(unconnectedApiCallDetails)).toBe(true);
	});

	it('does not match a call to a real service', () => {
		expect(isUnconnectedApiCall({ service: 'dvla' })).toBe(false);
	});
});

describe('isUndecidedRule', () => {
	it('recognises the placeholder rule', () => {
		expect(isUndecidedRule(undecidedRule)).toBe(true);
	});

	it('does not match a rule with a real path or a different operator', () => {
		expect(isUndecidedRule({ op: 'is_true', path: 'confirmed' })).toBe(false);
		expect(isUndecidedRule({ op: 'is_false', path: undecidedRule.path })).toBe(false);
	});

	it('does not match a condition that has no path', () => {
		expect(isUndecidedRule({ op: 'and', all: [undecidedRule] })).toBe(false);
	});
});
