<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import OnboardDraftPage from '$lib/components/OnboardDraftPage.svelte';
	import { saveDraft, setOpenDraft } from '$lib/drafts/draft-store';
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
	 * Saves the generated form as a new draft, marks it as the draft open in this browser tab, and opens it in the form
	 * editor. Says whether it did, because the browser may refuse to store the draft.
	 */
	async function openInEditor(): Promise<boolean> {
		if (!form?.success) return false;
		const { workflow } = form;
		const id = crypto.randomUUID();
		try {
			await saveDraft({ id, name: workflow.manifest.description, stage: 'Edit', workflow, positions: {} });
		} catch {
			return false;
		}
		setOpenDraft(id);

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
