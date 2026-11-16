<script lang="ts">
	import DraftProblemPage from '$lib/components/DraftProblemPage.svelte';
	import ServiceEditorPage from '$lib/service-editor/components/ServiceEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

{#if data.draft.ok}
	<!-- The draft names its entry process after the service, so that code names the service on the page. -->
	<ServiceEditorPage slug={data.draft.workflow.manifest.entry} workflow={data.draft.workflow} />
{:else}
	<DraftProblemPage problem={data.draft} startRoute="/onboard/service/method" />
{/if}
