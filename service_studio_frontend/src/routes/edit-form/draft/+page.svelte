<script lang="ts">
	import DraftProblemPage from '$lib/components/DraftProblemPage.svelte';
	import FormEditorPage from '$lib/form-editor/components/FormEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

{#if data.draft.ok}
	<FormEditorPage workflow={data.draft.workflow} />
{:else}
	<DraftProblemPage problem={data.draft} startRoute="/onboard/form/method" />
{/if}
