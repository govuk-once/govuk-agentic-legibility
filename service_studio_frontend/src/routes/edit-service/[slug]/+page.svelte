<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ProcessWorkspace from '$lib/service-editor/components/ProcessWorkspace.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import type { NodePositions } from '$lib/service-editor/graph/process-graph-types';
	import type { Process } from '$lib/schema/workflow/process';
	import { parseWorkflow, type WorkflowIssue } from '$lib/schema/workflow/validate';
	import { processToGraph, stepCount, visibleGraph } from '$lib/service-editor/graph/process-to-graph';
	import { tidyCode } from '$lib/graph-kit/tidy-code';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The workflow being edited. It starts as the one that was loaded and is replaced by a new copy with every
	// change. It starts again from the loaded one when another service is opened, and it is not saved.
	let workingWorkflow = $derived(data.workflow);

	// The id of the process on the graph. It starts on the entry process, which is the one the manifest
	// says the workflow starts in, and it starts again from there when another service is opened.
	let selectedProcessId = $derived(data.workflow.manifest.entry);
	// The schema check has already confirmed that every listed process exists.
	const selectedProcess = $derived(workingWorkflow.processes[selectedProcessId]);
	/**
	 * Takes in a changed process. The whole workflow is checked against the schema first, so a change that
	 * breaks it is refused and its problems are given back to be shown, and the workflow is left as it was.
	 */
	function changeProcess(updated: Process): WorkflowIssue[] {
		const result = parseWorkflow({
			manifest: workingWorkflow.manifest,
			processes: { ...workingWorkflow.processes, [selectedProcessId]: updated }
		});
		if (!result.ok) return result.issues;

		workingWorkflow = result.workflow;
		return [];
	}

	// Where the person has dragged boxes to, kept for each process while the page is open. It is only how the
	// graph is drawn, so it is not part of the workflow and is not saved.
	let draggedPositions = $state<Record<string, NodePositions>>({});
	const processKey = $derived(`${data.slug}:${selectedProcessId}`);
	const positions = $derived(draggedPositions[processKey] ?? {});

	function moveNodes(moved: NodePositions) {
		draggedPositions = { ...draggedPositions, [processKey]: { ...positions, ...moved } };
	}

	// Puts every box of the process on the graph back where the layout placed it.
	function tidyUp() {
		const { [processKey]: _removed, ...others } = draggedPositions;
		draggedPositions = others;
	}

	// Error routes are hidden at first so the main journey is easy to follow.
	let showErrorRoutes = $state(false);

	// The number of steps is the number of numbered boxes shown, so it matches the numbers on the graph and
	// the list.
	const steps = $derived(stepCount(visibleGraph(processToGraph(selectedProcess), showErrorRoutes)));
</script>

<svelte:head>
	<title>{tidyCode(data.slug)} | Service Studio</title>
</svelte:head>

<!-- The stage sequence sits inside the banner row, as it does on the original editor. -->
<ServiceHeader>
	<Progress stages={editStages} compact />
</ServiceHeader>

<main class="editor-page">
	<div class="editor-page__toolbar">
		<div class="editor-page__toolbar-summary">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0 editor-page__toolbar-title">{tidyCode(data.slug)}</h2>
			<div class="editor-page__process-picker">
				<label class="govuk-label govuk-!-margin-bottom-0" for="process-select">Process</label>
				<select class="govuk-select" id="process-select" bind:value={selectedProcessId}>
					{#each workingWorkflow.manifest.processes as listed (listed.process_id)}
						<option value={listed.process_id}>
							{tidyCode(listed.process_id)}{listed.process_id === workingWorkflow.manifest.entry
								? ' (entry process)'
								: ''}
						</option>
					{/each}
				</select>
			</div>
			<div class="editor-page__toolbar-stats">
				<span class="govuk-body govuk-!-margin-bottom-0 editor-page__stat">
					<strong>{steps}</strong>
					{steps === 1 ? 'step' : 'steps'}
				</span>
			</div>
		</div>

		<div class="editor-page__toolbar-controls">
			<label class="govuk-body govuk-!-margin-bottom-0 editor-page__toggle">
				<!-- Showing or hiding the error routes arranges the graph again, so boxes dragged before are put back. -->
				<input type="checkbox" bind:checked={showErrorRoutes} onchange={tidyUp} />
				Show error routes
			</label>
			{#if Object.keys(positions).length > 0}
				<button type="button" class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" onclick={tidyUp}>
					Tidy up
				</button>
			{/if}
			<a class="govuk-link" href={resolve('/edit-service')}>Choose a different service</a>
		</div>
	</div>

	<!-- The workspace is shown afresh for each process, and again when the error routes are shown or hidden,
		because the graph is arranged again then. Each time the view fits to the new graph and no state
		stays selected from the one before. -->
	{#key `${processKey}:${showErrorRoutes}`}
		<ProcessWorkspace
			process={selectedProcess}
			{showErrorRoutes}
			{positions}
			onMoveNodes={moveNodes}
			onChangeProcess={changeProcess}
			onOpenProcess={(processId) => (selectedProcessId = processId)}
		/>
	{/key}
</main>

<style>
	.editor-page {
		display: flex;
		flex-direction: column;
		height: calc(100vh - 74px);
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.editor-page__toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 20px;
		padding: 12px 40px;
		border-bottom: 1px solid #b1b4b6;
	}

	.editor-page__toolbar-summary {
		display: flex;
		align-items: center;
		gap: 15px;
		min-width: 0;
	}

	.editor-page__toolbar-title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.editor-page__process-picker {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.editor-page__toolbar-stats {
		flex-shrink: 0;
		display: flex;
		border: 1px solid #b1b4b6;
	}

	.editor-page__stat {
		padding: 5px 15px;
		background-color: #f3f2f1;
	}

	.editor-page__toolbar-controls {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 20px;
	}

	.editor-page__toggle {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.editor-page__toggle input {
		width: 20px;
		height: 20px;
		accent-color: #0b0c0c;
	}
</style>
