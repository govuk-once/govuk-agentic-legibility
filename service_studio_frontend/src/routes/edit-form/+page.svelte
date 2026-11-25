<script lang="ts">
	import { resolve } from '$app/paths';
	import ExamplePickerPage from '$lib/components/ExamplePickerPage.svelte';
	import { formExamples } from '$lib/examples/forms';
</script>

<svelte:head>
	<title>Edit and review the form | Service Studio</title>
</svelte:head>

<ExamplePickerPage
	subject="form"
	heading="Edit and review the form"
	intro="Choose a form below to see whether it matches the schema, then open the graph."
	examples={formExamples}
	openHref={(slug) => resolve('/edit-form/[slug]', { slug })}
/>
