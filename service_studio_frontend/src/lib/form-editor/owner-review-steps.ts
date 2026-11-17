import type { ReviewStepState } from '$lib/components/ReviewStep.svelte';

// The steps of the owner review, in the order they are done.
const ownerReviewStepLabels = ['Details', 'Review', 'Sign off'];

/**
 * Names the steps of the owner review with how far each one has got. Each page gives the state of every step, so the
 * labels are written once here.
 */
export function ownerReviewSteps(states: [ReviewStepState, ReviewStepState, ReviewStepState]) {
	return ownerReviewStepLabels.map((label, index) => ({ label, state: states[index] }));
}
