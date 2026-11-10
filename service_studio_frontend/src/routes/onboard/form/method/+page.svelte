<script lang="ts">
	import OnboardMethodPage from '$lib/components/OnboardMethodPage.svelte';
</script>

<svelte:head>
	<title>Choose a drafting method | Service Studio</title>
</svelte:head>

<OnboardMethodPage
	detailsRoute="/onboard/form/details"
	caption="Start a new form, step 1 of 2"
	automationHint="An assistant reads what is already on GOV.UK, plus anything you give it, and drafts a form journey and graph. Steps and conditions remain editable until published."
/>
