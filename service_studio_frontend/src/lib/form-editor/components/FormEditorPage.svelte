<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
	import type { Workflow } from '$lib/schema/workflow/workflow';
	import { formDeveloperStateTypes } from '../schema/form-states';
	import FormWorkspace from './FormWorkspace.svelte';

	// The page for looking at one form. A form is a single process, which the route has already checked, so the page
	// shows the process the manifest names as its entry.
	let { workflow }: { workflow: Workflow } = $props();

	const process = $derived(workflow.processes[workflow.manifest.entry]);

	// Developer states and the error routes are hidden at first so the questions are easy to follow. One tick shows both.
	let showDeveloperStates = $state(false);

	// The number of steps is the number of numbered boxes shown, so it matches the numbers on the graph and the list.
	const shown = $derived(
		visibleGraph(processToGraph(process, formDeveloperStateTypes), {
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
				<input type="checkbox" bind:checked={showDeveloperStates} />
				Show developer states
			</label>
			<a class="govuk-link govuk-body-s govuk-!-margin-bottom-0" href={resolve('/edit-form')}>Choose a different form</a>
		</div>
	</div>

	<!-- Shown afresh when the developer states are shown or hidden, because the graph is arranged again then. Each time
		the view fits to the new graph and no state stays selected from the one before. -->
	{#key showDeveloperStates}
		<FormWorkspace {process} {showDeveloperStates} />
	{/key}
</main>

<style>
	.form-editor-page {
		display: flex;
		flex-direction: column;
		height: calc(100vh - 74px);
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
