<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { editStages } from '$lib/components/progress-stages';
	import ProcessGraph from '$lib/graph/ProcessGraph.svelte';
	import { tidyCode } from '$lib/graph/tidy-code';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The graph shows the entry process, which is the one the manifest says the workflow starts in.
	// The schema check has already confirmed that this process exists.
	const entryProcess = $derived(data.workflow.processes[data.workflow.manifest.entry]);
	const stateCount = $derived(Object.keys(entryProcess.states).length);
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
			<div class="editor-page__toolbar-stats">
				<span class="govuk-body govuk-!-margin-bottom-0 editor-page__stat">
					<strong>{stateCount}</strong>
					{stateCount === 1 ? 'state' : 'states'} in this process
				</span>
			</div>
		</div>

		<a class="govuk-link" href={resolve('/edit-unified')}>Choose a different service</a>
	</div>

	<div class="editor-page__body">
		<div class="editor-page__canvas">
			<ProcessGraph process={entryProcess} />
		</div>
	</div>
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

	.editor-page__toolbar-stats {
		flex-shrink: 0;
		display: flex;
		border: 1px solid #b1b4b6;
	}

	.editor-page__stat {
		padding: 5px 15px;
		background-color: #f3f2f1;
	}

	.editor-page__body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.editor-page__canvas {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
	}
</style>
