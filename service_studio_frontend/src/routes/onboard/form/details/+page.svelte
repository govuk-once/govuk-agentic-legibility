<script lang="ts">
	import { resolve } from '$app/paths';
	import OnboardDetailsPage from '$lib/components/OnboardDetailsPage.svelte';
</script>

<svelte:head>
	<title>Describe the form | Service Studio</title>
</svelte:head>

<OnboardDetailsPage
	subject="form"
	backHref={resolve('/onboard/form/method')}
	actionHref={resolve('/onboard/form/draft')}
	caption="Start a new form, step 2 of 2"
	heading="Tell the assistant about the form"
	intro="It will use this, plus what is already on GOV.UK, to draft the form journey and graph."
	initial={{ name: '', description: '', link: '' }}
/>
