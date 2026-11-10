<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import OnboardDraftPage from '$lib/components/OnboardDraftPage.svelte';
	import { saveDraft } from '$lib/service-editor/draft-store';
	import { processToGraph, stepCount, visibleGraph } from '$lib/process-graph/process-to-graph';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	// The process the draft opens on. The checks have already confirmed that the manifest's entry process exists.
	const process = $derived(form?.success ? form.workflow.processes[form.workflow.manifest.entry] : undefined);

	// The steps are counted the way the editor counts them, so the number here matches the one on the editing page.
	const stepTotal = $derived(process ? stepCount(visibleGraph(processToGraph(process), { showErrorRoutes: false })) : 0);

	// A decision is a branch, so the count matches the diamonds the editor will show.
	const branchCount = $derived(process ? Object.values(process.states).filter((state) => state.type === 'choice').length : 0);

	/**
	 * Holds the draft in this browser tab and opens it in the editor, which is a different page and so reads it
	 * from there. Says whether it did, because the browser may refuse to hold the draft.
	 */
	async function openInEditor(): Promise<boolean> {
		if (!form?.success || !saveDraft(form.workflow)) return false;

		await goto(resolve('/edit-service/draft'));
		return true;
	}
</script>

<svelte:head>
	<title>Review the first draft | Service Studio</title>
</svelte:head>

<OnboardDraftPage
	result={form}
	subject="service"
	detailsRoute="/onboard/service/details"
	{stepTotal}
	{branchCount}
	onEdit={openInEditor}
/>
