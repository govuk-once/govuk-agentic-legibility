import type { ReviewStepState } from '$lib/components/ReviewStep.svelte';

/*
	The steps of each review, in the order they are done. Each page gives the state of every step, so the labels are
	written once here.
*/

// Pairs each label with the state its page gives it.
function labelled(labels: readonly string[], states: readonly ReviewStepState[]) {
	return labels.map((label, index) => ({ label, state: states[index] }));
}

// The steps of the technical review: the settings for the whole journey, the API calls, then each developer step.
export function techReviewSteps(states: [ReviewStepState, ReviewStepState, ReviewStepState, ReviewStepState]) {
	return labelled(['Workflow settings', 'Flex connections', 'Step values', 'Review and send'], states);
}

// The steps of the owner review.
export function ownerReviewSteps(states: [ReviewStepState, ReviewStepState, ReviewStepState]) {
	return labelled(['Details', 'Review', 'Sign off'], states);
}
