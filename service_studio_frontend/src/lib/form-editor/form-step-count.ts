import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { formHiddenStateTypes } from './schema/form-states';

/**
 * Counts the steps of a form as the editor first shows it, with the developer states and the error routes hidden, so
 * the count saved with a draft does not change with what the editor happened to be showing when it was saved.
 */
export function formStepCount(process: WorkingProcess): number {
	return stepCount(visibleGraph(processToGraph(process, formHiddenStateTypes), { showErrorRoutes: false, showDeveloperSteps: false }));
}
