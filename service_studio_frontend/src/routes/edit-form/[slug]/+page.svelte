<script lang="ts">
	import FormEditorPage from '$lib/form-editor/components/FormEditorPage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<!-- The page is shown afresh for each form, so the shapes placed on the canvas of one form and the boxes dragged on
	it never carry over to another. -->
{#key data.slug}
	<FormEditorPage workflow={data.workflow} />
{/key}
