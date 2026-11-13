import { describe, expect, it } from 'vitest';
import { exampleWorkflows } from './example-states';
import {
	defaultEndStatus,
	isUndecidedRule,
	isUnconnectedApiCall,
	placeholderOwner,
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
