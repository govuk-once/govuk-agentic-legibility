import type { CallState } from './call-state';
import type { Condition } from './condition';
import type { CompletionStatus } from './states';

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
export const unconnectedCallDetails = {
	method: 'GET',
	service: 'unconnected_service',
	url: '/unconnected'
} as const satisfies Pick<CallState, 'method' | 'service' | 'url'>;

/**
 * Tells whether a call still holds the placeholder API details. The editor uses this to show that
 * the step needs connecting, and a check can use it to warn before the workflow is sent.
 */
export function isUnconnectedCall(call: Pick<CallState, 'service'>): boolean {
	return call.service === unconnectedCallDetails.service;
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
