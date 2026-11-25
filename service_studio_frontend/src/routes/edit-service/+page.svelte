<script lang="ts">
	import { resolve } from '$app/paths';
	import ExamplePickerPage from '$lib/components/ExamplePickerPage.svelte';
	import { serviceExamples } from '$lib/examples/services';
</script>

<svelte:head>
	<title>Edit and review the journey (unified schema) | Service Studio</title>
</svelte:head>

<ExamplePickerPage
	subject="service"
	heading="Edit and review the journey"
	intro="This page works on the unified schema. Choose a service below to see whether it matches the schema, then open the graph."
	examples={serviceExamples}
	openHref={(slug) => resolve('/edit-service/[slug]', { slug })}
/>
