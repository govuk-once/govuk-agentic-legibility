import { describeDuration } from '$lib/process-graph/describe-value';
import { placeholderApiCallDefaults } from '$lib/schema/workflow/placeholders';
import type { Manifest, Workflow } from '$lib/schema/workflow/workflow';
import { flexConnections } from '$lib/form-editor/flex-connections';
import { techReviewChecked } from '$lib/form-editor/step-values/step-values';

/*
	The technical review written in words, for the summary on its Review and send page and for the owner review.
*/

/**
 * Writes the workflow settings of a manifest in words: how long a run may last, and the time limit, tries and pause
 * every API call uses unless it sets its own. A value that is not set is left out of the sentence.
 */
export function describeWorkflowSettings(manifest: Manifest): { runTimeout: string; apiCalls: string } {
	const callDefaults = manifest.defaults.api_call;
	const timeouts = callDefaults?.timeouts ?? placeholderApiCallDefaults.timeouts;
	const retry = callDefaults?.retry ?? placeholderApiCallDefaults.retry;
	const parts = [
		timeouts.start_to_close && `time limit ${describeDuration(timeouts.start_to_close)}`,
		retry.max_attempts !== undefined && `tried ${retry.max_attempts} ${retry.max_attempts === 1 ? 'time' : 'times'}`,
		retry.initial_interval && `${describeDuration(retry.initial_interval)} between tries`
	].filter(Boolean);
	return { runTimeout: describeDuration(manifest.executor.run_timeout), apiCalls: parts.join(', ') };
}

/**
 * Tells whether a sent technical review has finished with a form: every API call is connected and every developer step
 * holds the time the review that checked it was sent. A form with neither has nothing to review, so it is finished.
 */
export function isTechReviewFinished(workflow: Workflow): boolean {
	const connections = flexConnections(workflow.processes[workflow.manifest.entry]);
	const checked = techReviewChecked(workflow);
	return connections.connected === connections.total && checked.checked === checked.total;
}
