<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ProcessWorkspace from '$lib/service-editor/components/ProcessWorkspace.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import { noDrafts, type DraftSet } from '$lib/process-graph/drafts';
	import type { NodePositions } from '$lib/process-graph/process-graph-types';
	import type { WorkingProcess, WorkingWorkflow } from '$lib/schema/workflow/working-process';
	import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
	import { tidyCode } from '$lib/graph-kit/tidy-code';
	import type { Workflow } from '$lib/schema/workflow/workflow';

	// The editing page for one service. It takes the service's code, which names it on the page, and its workflow. The
	// examples and a generated draft are both shown with it, so the page is written once.
	let { slug, workflow }: { slug: string; workflow: Workflow } = $props();

	// The workflow being edited. It starts as the one that was loaded and is replaced by a new copy with every
	// change. It starts again from the loaded one when another service is opened, and it is not saved. It is not
	// checked against the schema while it is being edited, because a journey is allowed to be unfinished then.
	let workingWorkflow = $derived<WorkingWorkflow>(workflow);

	// The id of the process on the graph. It starts on the entry process, which is the one the manifest
	// says the workflow starts in, and it starts again from there when another service is opened.
	let selectedProcessId = $derived(workflow.manifest.entry);
	// The schema check has already confirmed that every listed process exists.
	const selectedProcess = $derived(workingWorkflow.processes[selectedProcessId]);
	// Takes in a changed process and keeps it as the process on the graph. The other processes are the same objects as before.
	function changeProcess(updated: WorkingProcess) {
		workingWorkflow = { ...workingWorkflow, processes: { ...workingWorkflow.processes, [selectedProcessId]: updated } };
	}

	// Where the person has dragged boxes to, kept for each process while the page is open. It is only how the
	// graph is drawn, so it is not part of the workflow and is not saved.
	let draggedPositions = $state<Record<string, NodePositions>>({});
	const processKey = $derived(`${slug}:${selectedProcessId}`);
	const positions = $derived(draggedPositions[processKey] ?? {});

	function moveNodes(moved: NodePositions) {
		draggedPositions = { ...draggedPositions, [processKey]: { ...positions, ...moved } };
	}

	// The shapes placed from the palette that are not in the process yet, kept for each process while the page is
	// open. A workflow can have several processes, and the graph is built again when another one is shown or when the
	// error routes are shown or hidden, so they are held here to last through both. Like the positions they are only
	// how the graph is drawn, so they are not part of the workflow and are not saved.
	let draftSets = $state.raw<Record<string, DraftSet>>({});
	const drafts = $derived(draftSets[processKey] ?? noDrafts);

	// Counts how many times the whole graph has been arranged again since it was first drawn. Between arrangements
	// every box keeps its place.
	let layoutRound = $state(0);

	// Arranges the graph of the process again and forgets where its boxes were dragged to. Tidy up does this, and so
	// does moving a step in the journey, so the graph follows the new order of the list.
	function tidyUp() {
		const { [processKey]: _removed, ...others } = draggedPositions;
		draggedPositions = others;
		layoutRound += 1;
	}

	// Error routes are hidden at first so the main journey is easy to follow.
	let showErrorRoutes = $state(false);

	// The number of steps is the number of numbered boxes shown, so it matches the numbers on the graph and
	// the list.
	const steps = $derived(stepCount(visibleGraph(processToGraph(selectedProcess), { showErrorRoutes })));
</script>

<svelte:head>
	<title>{tidyCode(slug)} | Service Studio</title>
</svelte:head>

<!-- The stage sequence sits inside the banner row. -->
<ServiceHeader>
	<Progress stages={editStages} compact />
</ServiceHeader>

<main class="editor-page">
	<div class="editor-page__toolbar">
		<div class="editor-page__toolbar-summary">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0 editor-page__toolbar-title">{tidyCode(slug)}</h2>
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
			<div class="govuk-checkboxes govuk-checkboxes--small">
				<div class="govuk-checkboxes__item">
					<!-- Showing or hiding the error routes arranges the graph again, so boxes dragged before are put back. -->
					<input class="govuk-checkboxes__input" id="show-error-routes" type="checkbox" bind:checked={showErrorRoutes} onchange={tidyUp} />
					<label class="govuk-label govuk-checkboxes__label" for="show-error-routes">Show error routes</label>
				</div>
			</div>
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
			{layoutRound}
			onMoveNodes={moveNodes}
			onRearrange={tidyUp}
			{drafts}
			onChangeDrafts={(changed) => (draftSets = { ...draftSets, [processKey]: changed })}
			onChangeProcess={changeProcess}
			onOpenProcess={(processId) => (selectedProcessId = processId)}
		/>
	{/key}
</main>

<style>
	/* The page takes the height left under the service header, whatever height the header is, so the editor reaches
		the bottom of the window with no gap. It does not grow with its content, which scrolls inside the canvas and
		the side panel instead. */
	.editor-page {
		display: flex;
		flex-direction: column;
		flex: 1 1 0;
		min-height: 0;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.editor-page__toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 20px;
		padding: 10px 40px;
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

	/* GOV.UK limits a checkbox label to the width of its group less the box, and a group in a row of controls is only
		as wide as its words, so the label would wrap onto two lines. Each label is kept on one line instead. */
	.editor-page__toolbar-controls :global(.govuk-checkboxes__label) {
		white-space: nowrap;
	}
</style>
