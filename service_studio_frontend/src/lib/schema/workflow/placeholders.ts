import type { ApiCallState, RetryPolicy, Timeouts } from './api-call-state';
import type { Condition } from './condition';
import type { CompletionStatus, EndState } from './states';

/*
	Placeholder values for details that are filled in at a later review, not while the journey is
	being drawn. Each one is a real value that passes validation, so a draft can be saved and checked
	straight away, and each can be recognised later, so the editor can say what is still missing.
	They live in one file so the editor, the onboarding step and the checks all agree on them.
*/

/**
 * The service owner and contact before they are entered at the review stage. The contact is a valid
 * email address on a reserved example domain, so it passes validation and can never reach a person.
 */
export const placeholderOwner = {
	owner: 'To be confirmed',
	contact: 'to.be.confirmed@example.com'
} as const;

/**
 * The API details of a call that has not been connected to a real service yet. The method, service
 * and url come from the technical review, which is after the journey is drawn, so a new API step
 * holds these until then. The service name is the part used to recognise an unconnected call.
 */
export const unconnectedApiCallDetails = {
	method: 'GET',
	service: 'unconnected_service',
	url: '/unconnected'
} as const satisfies Pick<ApiCallState, 'method' | 'service' | 'url'>;

/**
 * Tells whether a call still holds the placeholder API details. The editor uses this to show that
 * the step needs connecting, and a check can use it to warn before the workflow is sent.
 */
export function isUnconnectedApiCall(call: Pick<ApiCallState, 'service'>): boolean {
	return call.service === unconnectedApiCallDetails.service;
}

/**
 * The rule given to a decision drawn by hand, before anyone has said what it should test. It tests
 * a variable that nothing sets, so it is valid but never matches and the default route is taken.
 */
export const undecidedRule = { op: 'is_true', path: 'rule_to_be_decided' } as const satisfies Condition;

/**
 * Tells whether a condition is the placeholder rule, so the editor can show that the decision
 * still needs a rule.
 */
export function isUndecidedRule(condition: Condition): boolean {
	return condition.op === undecidedRule.op && 'path' in condition && condition.path === undecidedRule.path;
}

/**
 * The status given to an end state that is drawn without one. A person marks how a journey ended
 * in a later step, and until then it counts as a normal finish.
 */
export const defaultEndStatus: CompletionStatus = 'success';

/**
 * The question given to an input that is made from another kind of step, when the old step had no words
 * to carry over. A person writes the real question after the type is changed.
 */
export const placeholderQuestion = 'Question to be confirmed';

/**
 * The message given to an output that is made from another kind of step, when the old step had no words
 * to carry over. A person writes the real message after the type is changed.
 */
export const placeholderMessage = 'Message to be confirmed';

/**
 * The answer type given to an input made from another kind of step. Text is the most general answer, so
 * the step is valid straight away and the person picks the right type later.
 */
export const placeholderAnswerKind = 'string';

/**
 * How long a wait made from another kind of step lasts until a person sets it. One minute is a guess and
 * is not from the unified document, so it is kept here to be easy to change.
 */
export const placeholderWaitDuration = 'PT1M';

/**
 * The name of the variable that holds the answer of an input made from another kind of step. It is built
 * from the code of the state so it is unique, and any character a variable name cannot hold is replaced.
 */
export function placeholderAnswerVariable(stateCode: string): string {
	return `answer_${stateCode.replace(/[^A-Za-z0-9_]/g, '_')}`;
}

/**
 * The first part of a workflow id before the owner is known. An id needs at least two parts joined by dots, and
 * the first part normally names the owning team, so this stands in for it until the owner is confirmed.
 */
export const placeholderNamespace = 'draft';

/**
 * How long a whole run of the workflow may last before the executor stops it. Fourteen days is the limit the
 * example services use. A real limit is set at the technical review.
 */
export const placeholderRunTimeout = 'P14D';

/**
 * The time limit and retry policy that every call uses unless a call says otherwise. They are the same as the
 * example services use, so a draft behaves like a real workflow until the technical review sets its own.
 */
export const placeholderApiCallDefaults: { timeouts: Timeouts; retry: RetryPolicy } = {
	timeouts: { start_to_close: 'PT15S' },
	retry: {
		max_attempts: 3,
		initial_interval: 'PT1S',
		backoff_coefficient: 2,
		max_interval: 'PT30S',
		retry_on: ['5xx', '429', 'timeout', 'connection']
	}
};

/**
 * How the executor names and reuses each run of a draft workflow. The name is the slug of the workflow, and a
 * repeat run is allowed, because refusing one would stop a second person using the draft. The technical review
 * sets the real template and policy.
 */
export function placeholderExecutor(slug: string) {
	return {
		workflow_id_template: slug,
		id_reuse_policy: 'allow_duplicate',
		run_timeout: placeholderRunTimeout,
		search_attributes: {}
	} as const;
}

/**
 * The end that every call leads to when it reports an error and nobody has said where it should go. It finishes
 * the journey as failed, which is the most common choice in the example services. The technical review points each
 * call at the right place.
 */
export const placeholderFailedEnd: EndState = { state_type: 'end', status: 'failed', name: 'Something went wrong' };
