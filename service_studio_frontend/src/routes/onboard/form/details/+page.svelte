<script lang="ts">
	import OnboardDetailsPage from '$lib/components/OnboardDetailsPage.svelte';
</script>

<svelte:head>
	<title>Describe the form | Service Studio</title>
</svelte:head>

<!-- There is no actionRoute yet, because a form draft cannot be generated until its own onboarding is built. -->
<OnboardDetailsPage
	subject="form"
	backRoute="/onboard/form/method"
	caption="Start a new form, step 2 of 2"
	heading="Tell the assistant about the form"
	intro="It will use this, plus what is already on GOV.UK, to draft the form journey and graph."
	initial={{ name: '', description: '', link: '' }}
/>
