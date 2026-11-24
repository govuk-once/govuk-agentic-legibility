<script lang="ts">
	import { resolve } from '$app/paths';
	import DraftProblemPage from '$lib/components/DraftProblemPage.svelte';
	import FormEditorPage from '$lib/form-editor/components/FormEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

{#if data.opened.ok}
	{@const draft = data.opened.draft}
	<FormEditorPage workflow={draft.workflow} draftId={draft.id} savedPositions={draft.positions} />
{:else}
	<DraftProblemPage problem={data.opened} startHref={resolve('/onboard/form/method')} />
{/if}
