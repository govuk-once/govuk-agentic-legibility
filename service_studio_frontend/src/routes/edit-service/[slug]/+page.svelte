<script lang="ts">
	import ServiceEditorPage from '$lib/service-editor/components/ServiceEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<ServiceEditorPage slug={data.slug} workflow={data.workflow} />
