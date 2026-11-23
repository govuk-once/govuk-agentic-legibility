import { describe, expect, it } from 'vitest';
import { formExamples } from '$lib/examples/forms';
import { inputBefore } from '$lib/schema/workflow/choice-answers';
import type { WorkingState } from '$lib/schema/workflow/working-process';
import { decisionRowLabels, ruleRowLabels, shortAnswerLabel } from '../decision-rows';

type Choice = Extract<WorkingState, { state_type: 'choice' }>;
type Input = Extract<WorkingState, { state_type: 'input' }>;

const yesOrNo = { state_type: 'input', prompt: 'Is it right?', schema: { kind: 'boolean' }, assign: 'ok' } as Input;
const chooseOne = {
	state_type: 'input',
	prompt: 'How?',
	schema: { kind: 'select_one', options: ['post', 'online', 'phone'].map((value) => ({ value, label: value })) },
	assign: 'method'
} as Input;
const undecided = { op: 'is_true', path: 'rule_to_be_decided' };
const choice = (conditions: unknown[]) => ({ state_type: 'choice', rules: conditions.map((when) => ({ when, next: 'a' })), default: 'b' }) as Choice;

describe('shortAnswerLabel', () => {
	it('keeps only the short answer of an option written with a dash and an explanation', () => {
		expect(shortAnswerLabel('No - the first vessel owner will receive all licences, notices and variations')).toBe('No');
		expect(shortAnswerLabel('Yes - I want to license a registered vessel')).toBe('Yes');
	});

	it('keeps a short option as it is', () => {
		expect(shortAnswerLabel("I want to use somebody else's details")).toBe("I want to use somebody else's details");
	});

	it('cuts a long option with no dash to a fixed length and shows that there was more', () => {
		const cut = shortAnswerLabel("No I don't want to nominate a second person to receive licence variation notifications");
		expect(cut).toBe("No I don't want to nominate a second per...");
		expect(cut.length).toBeLessThanOrEqual(43);
	});
});

describe('decisionRowLabels', () => {
	it('names the two ways out of a decision on a yes or no input by yes and no', () => {
		expect(decisionRowLabels(choice([{ op: 'is_true', path: 'ok' }]), yesOrNo)).toEqual(['If the answer is Yes', 'If the answer is No']);
		expect(decisionRowLabels(choice([{ op: 'is_false', path: 'ok' }]), yesOrNo)).toEqual(['If the answer is No', 'If the answer is Yes']);
	});

	it('names the last way out as anything else when more than one answer is left over', () => {
		expect(decisionRowLabels(choice([{ op: 'eq', path: 'method', value: 'post' }]), chooseOne)).toEqual([
			'If the answer is post',
			'If the answer is anything else'
		]);
	});

	it('names the last way out by the one answer left over', () => {
		const rules = [{ op: 'eq', path: 'method', value: 'post' }, { op: 'eq', path: 'method', value: 'online' }];
		expect(decisionRowLabels(choice(rules), chooseOne)[2]).toBe('If the answer is phone');
	});

	it('numbers every way out of a decision drawn by hand, whose rules are not about an answer yet', () => {
		expect(decisionRowLabels(choice([undecided, undecided]), yesOrNo)).toEqual(['Answer 1', 'Answer 2', 'Answer 3']);
	});

	it('numbers every way out of a decision that follows no input', () => {
		expect(decisionRowLabels(choice([{ op: 'is_true', path: 'ok' }]), undefined)).toEqual(['Answer 1', 'Answer 2']);
	});

	it('names every way out of every decision in the form examples by an answer, with none numbered', () => {
		let decisions = 0;
		// The demo form is left out, because its added decision follows an API call and is named by its rule.
		for (const example of formExamples.filter((candidate) => !candidate.slug.endsWith('_with_submit'))) {
			for (const process of Object.values(example.workflow?.processes ?? {})) {
				for (const [code, state] of Object.entries(process.states)) {
					if (state.state_type !== 'choice') continue;
					decisions += 1;
					const labels = decisionRowLabels(state, inputBefore(process, code)?.input);
					expect(labels, `${example.slug}: ${code}`).toHaveLength(state.rules.length + 1);
					for (const label of labels) expect(label, `${example.slug}: ${code}`).toMatch(/^If the answer is /);
				}
			}
		}
		expect(decisions).toBe(43);
	});
});

describe('ruleRowLabels', () => {
	it('names each way out by its rule in words, then otherwise', () => {
		expect(ruleRowLabels(choice([{ op: 'eq', path: 'check.status', value: 'done' }]))).toEqual([
			'If check.status is "done"',
			'Otherwise'
		]);
	});
});
