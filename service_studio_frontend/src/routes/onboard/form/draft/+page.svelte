<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import OnboardDraftPage from '$lib/components/OnboardDraftPage.svelte';
	import { saveDraft } from '$lib/form-editor/draft-store';
	import { formDeveloperStateTypes } from '$lib/form-editor/schema/form-states';
	import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	// The process the draft opens on. The checks have already confirmed that the manifest's entry process exists.
	const process = $derived(form?.success ? form.workflow.processes[form.workflow.manifest.entry] : undefined);

	// The graph as the form editor first shows it, with the developer states hidden, so the counts here match it.
	const shown = $derived(
		process
			? visibleGraph(processToGraph(process, formDeveloperStateTypes), { showErrorRoutes: false, showDeveloperSteps: false })
			: undefined
	);
	const stepTotal = $derived(shown ? stepCount(shown) : 0);

	// A decision is a branch, so the count matches the diamonds the editor will show.
	const branchCount = $derived(shown ? shown.nodes.filter((node) => node.type === 'condition').length : 0);

	/**
	 * Holds the draft in this browser tab and opens it in the form editor, which is a different page and so reads it
	 * from there. Says whether it did, because the browser may refuse to hold the draft.
	 */
	async function openInEditor(): Promise<boolean> {
		if (!form?.success || !saveDraft(form.workflow)) return false;

		await goto(resolve('/edit-form/draft'));
		return true;
	}
</script>

<svelte:head>
	<title>Review the first draft | Service Studio</title>
</svelte:head>

<OnboardDraftPage
	result={form}
	subject="form"
	detailsHref={resolve('/onboard/form/details')}
	{stepTotal}
	{branchCount}
	onEdit={openInEditor}
/>
