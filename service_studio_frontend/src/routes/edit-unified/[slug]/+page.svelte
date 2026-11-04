<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ProcessWorkspace from '$lib/components/ProcessWorkspace.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import { processToGraph, stepCount, visibleGraph } from '$lib/graph/process-to-graph';
	import { tidyCode } from '$lib/graph/tidy-code';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The id of the process on the graph. It starts on the entry process, which is the one the manifest
	// says the workflow starts in, and it starts again from there when another service is opened.
	let selectedProcessId = $derived(data.workflow.manifest.entry);
	// The schema check has already confirmed that every listed process exists.
	const selectedProcess = $derived(data.workflow.processes[selectedProcessId]);
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
					{#each data.workflow.manifest.processes as listed (listed.process_id)}
						<option value={listed.process_id}>
							{tidyCode(listed.process_id)}{listed.process_id === data.workflow.manifest.entry
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
				<input type="checkbox" bind:checked={showErrorRoutes} />
				Show error routes
			</label>
			<a class="govuk-link" href={resolve('/edit-unified')}>Choose a different service</a>
		</div>
	</div>

	<!-- The workspace is shown afresh for each process, so the graph fits to the new process and no state
		stays selected from the one before. -->
	{#key `${data.slug}:${selectedProcessId}`}
		<ProcessWorkspace
			process={selectedProcess}
			{showErrorRoutes}
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
