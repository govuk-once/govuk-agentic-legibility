<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ContextItem } from '$lib/components/context';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import { noDrafts, type DraftSet } from '$lib/process-graph/drafts';
	import type { NodePositions } from '$lib/process-graph/process-graph-types';
	import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
	import type { WorkingProcess, WorkingWorkflow } from '$lib/schema/workflow/working-process';
	import type { Workflow } from '$lib/schema/workflow/workflow';
	import { saveFormForReview } from '../review-store';
	import { formHiddenStateTypes } from '../schema/form-states';
	import FormWorkspace from './FormWorkspace.svelte';

	// The page for editing one form. A form is a single process, which the route has already checked, so the page
	// edits the process the manifest names as its entry.
	let { workflow }: { workflow: Workflow } = $props();

	// The form being edited. It starts as the one that was loaded and is replaced by a new copy with every change. It
	// is not saved, and it is not checked against the schema while it is being edited, because a journey is allowed
	// to be unfinished then.
	let workingWorkflow = $derived<WorkingWorkflow>(workflow);

	const processId = $derived(workflow.manifest.entry);
	const process = $derived(workingWorkflow.processes[processId]);

	// Takes in the changed process and keeps it as the one on the graph.
	function changeProcess(updated: WorkingProcess) {
		workingWorkflow = { ...workingWorkflow, processes: { ...workingWorkflow.processes, [processId]: updated } };
	}

	// Holds the edited form in the browser tab and goes on to owner review, so the review pages can open what was
	// edited here. The form has passed its check by now, and the review pages check it again when they load it.
	function sendToOwnerReview() {
		saveFormForReview(workingWorkflow);
		goto(resolve('/owner-review/form'));
	}

	// Where the person has dragged boxes to. It is only how the graph is drawn, so it is not part of the form and is
	// not saved.
	let positions = $state<NodePositions>({});

	function moveNodes(moved: NodePositions) {
		positions = { ...positions, ...moved };
	}

	// Counts how many times the whole graph has been arranged again since it was first drawn. Between arrangements
	// every box keeps its place.
	let layoutRound = $state(0);

	// Arranges the whole graph again and forgets where boxes were dragged to. Moving a step in the journey does this,
	// so the graph follows the new order of the list.
	function rearrange() {
		positions = {};
		layoutRound += 1;
	}

	// The shapes placed from the palette that are not in the process yet. They are held here and not beside the
	// graph, because the graph is built again when the developer states are shown or hidden. Like the positions they
	// are only how the graph is drawn, so they are not part of the form and are not saved.
	let drafts = $state.raw<DraftSet>(noDrafts);

	// The context added for the agent, by the code of the step it was added to. It lasts while the page is open. It
	// is not part of the form and is not saved.
	let stepContext = $state.raw<Record<string, ContextItem[]>>({});

	// Developer states and the error routes are hidden at first so the questions are easy to follow. One tick shows both.
	let showDeveloperStates = $state(false);

	// The number of steps is the number of numbered boxes shown, so it matches the numbers on the graph and the list.
	const shown = $derived(
		visibleGraph(processToGraph(process, formHiddenStateTypes), {
			showErrorRoutes: showDeveloperStates,
			showDeveloperSteps: showDeveloperStates
		})
	);
	const steps = $derived(stepCount(shown));

	// A branch is a decision, so the count matches the diamonds on the graph.
	const branches = $derived(shown.nodes.filter((node) => node.type === 'condition').length);
</script>

<svelte:head>
	<title>{workflow.manifest.description} | Service Studio</title>
</svelte:head>

<ServiceHeader>
	<Progress stages={editStages} compact />
</ServiceHeader>

<main class="form-editor-page">
	<div class="form-editor-page__toolbar">
		<div class="form-editor-page__toolbar-summary">
			<h2 class="govuk-heading-s govuk-!-margin-bottom-0 form-editor-page__toolbar-title">{workflow.manifest.description}</h2>
			<div class="form-editor-page__toolbar-stats">
				<span class="govuk-body-s govuk-!-margin-bottom-0 form-editor-page__stat">
					<strong>{steps}</strong>
					{steps === 1 ? 'step' : 'steps'}
				</span>
				<span class="govuk-body-s govuk-!-margin-bottom-0 form-editor-page__stat">
					<strong>{branches}</strong>
					{branches === 1 ? 'branch' : 'branches'}
				</span>
			</div>
		</div>

		<div class="form-editor-page__toolbar-controls">
			<label class="govuk-body-s govuk-!-margin-bottom-0 form-editor-page__toggle">
				<!-- Showing or hiding the developer states arranges the graph again, so boxes dragged before are put back. -->
				<input type="checkbox" bind:checked={showDeveloperStates} onchange={() => (positions = {})} />
				Show developer states
			</label>
			<a class="govuk-link govuk-body-s govuk-!-margin-bottom-0" href={resolve('/edit-form')}>Choose a different form</a>
		</div>
	</div>

	<!-- Shown afresh when the developer states are shown or hidden, because the graph is arranged again then. Each time
		the view fits to the new graph and no state stays selected from the one before. -->
	{#key showDeveloperStates}
		<FormWorkspace
			{process}
			{showDeveloperStates}
			{positions}
			{layoutRound}
			onMoveNodes={moveNodes}
			onRearrange={rearrange}
			{drafts}
			onChangeDrafts={(changed) => (drafts = changed)}
			onChangeProcess={changeProcess}
			{stepContext}
			onChangeStepContext={(code, items) => (stepContext = { ...stepContext, [code]: items })}
			onSendToOwnerReview={sendToOwnerReview}
		/>
	{/key}
</main>

<style>
	/* The page takes the height left under the service header, whatever height the header is, so the editor reaches
		the bottom of the window with no gap. It does not grow with its content, which scrolls inside the canvas and
		the side panel instead. */
	.form-editor-page {
		display: flex;
		flex-direction: column;
		flex: 1 1 0;
		min-height: 0;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	/* Padding matches the service header's own 40px so the title lines up under GOV.UK, and the controls line up under
		the Experimental prototype flag. */
	.form-editor-page__toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 20px;
		padding: 12px 40px;
		border-bottom: 1px solid #b1b4b6;
	}

	.form-editor-page__toolbar-summary {
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
	}

	.form-editor-page__toolbar-title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.form-editor-page__toolbar-stats {
		flex-shrink: 0;
		display: flex;
		border: 1px solid #b1b4b6;
	}

	.form-editor-page__stat {
		padding: 6px 14px;
		background-color: #f3f2f1;
	}

	.form-editor-page__stat + .form-editor-page__stat {
		border-left: 1px solid #b1b4b6;
	}

	.form-editor-page__toolbar-controls {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 15px;
	}

	.form-editor-page__toggle {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.form-editor-page__toggle input {
		width: 16px;
		height: 16px;
		accent-color: #0b0c0c;
	}
</style>
