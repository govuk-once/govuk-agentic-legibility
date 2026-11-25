import { describeCondition } from '$lib/process-graph/describe-value';
import { answerChoices, answerOfCondition } from '$lib/schema/workflow/choice-answers';
import type { WorkingState } from '$lib/schema/workflow/working-process';

/*
	The words shown beside each way out of a decision on its card. A decision has one way out for each of its rules
	and one more that is taken when no rule matches. A person does not think in rules, so each way out is named by
	the answer that leads to it, in the words of the question before the decision.

	1. A way out whose rule is for one of the question's answers is named by that answer.
	2. The last way out is taken when no rule matches. When every rule is for an answer and exactly one answer is
	   left over, it is named by that answer. When several are left over it is named as anything else.
	3. A decision drawn by hand has no answers yet, and so does a decision that follows no question. Its ways out
	   are numbered, so each can still be told from the others.
	4. A decision that follows a developer step, such as an API call, tests what that step saved and not an answer.
	   Its ways out are named by their rules in words, and the last one is named as otherwise.
*/

type WorkingChoice = Extract<WorkingState, { state_type: 'choice' }>;
type WorkingInput = Extract<WorkingState, { state_type: 'input' }>;

// The most characters of an answer that are shown, so a long option does not fill the card.
const answerLabelLength = 40;

/**
 * Shortens the words of an answer for a label. An option written as a short answer, a dash and an explanation,
 * such as "No - the first owner receives the licence", is cut to the short answer. Any other long option is cut to
 * a fixed length, with dots to show that there was more.
 */
export function shortAnswerLabel(label: string): string {
	const beforeDash = label.split(' - ')[0].trim();
	const words = beforeDash.length > 0 && beforeDash.length < label.length ? beforeDash : label.trim();
	return words.length > answerLabelLength ? `${words.slice(0, answerLabelLength).trimEnd()}...` : words;
}

/**
 * Names every way out of a decision, in order: one for each rule and then the one taken when no rule matches. The
 * question is the one the decision follows, or nothing when it follows no single question.
 */
export function decisionRowLabels(choice: WorkingChoice, question: WorkingInput | undefined): string[] {
	const answers = question ? answerChoices(question) : [];
	const labelOf = (value: string) => `If the answer is ${shortAnswerLabel(answers.find((answer) => answer.value === value)?.label ?? value)}`;

	// The answer each rule is for, or nothing for a rule that is not about one of the question's answers.
	const ruleAnswers = choice.rules.map((rule) => (question ? answerOfCondition(question, rule.when) : undefined));
	const ruleLabels = ruleAnswers.map((answer, index) => (answer === undefined ? `Answer ${index + 1}` : labelOf(answer)));

	// The last way out can only be named by an answer when every rule before it is.
	if (ruleAnswers.some((answer) => answer === undefined)) return [...ruleLabels, `Answer ${choice.rules.length + 1}`];

	const leftOver = answers.filter((answer) => !ruleAnswers.includes(answer.value));
	return [...ruleLabels, leftOver.length === 1 ? labelOf(leftOver[0].value) : 'If the answer is anything else'];
}

/**
 * Names every way out of a decision by its rule in words, such as 'If job.status is "done"', and then "Otherwise" for
 * the way taken when no rule matches. Used for a decision that tests what a developer step saved.
 */
export function ruleRowLabels(choice: WorkingChoice): string[] {
	return [...choice.rules.map((rule) => `If ${describeCondition(rule.when)}`), 'Otherwise'];
}
