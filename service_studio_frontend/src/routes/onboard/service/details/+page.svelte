<script lang="ts">
	import OnboardDetailsPage from '$lib/components/OnboardDetailsPage.svelte';
</script>

<svelte:head>
	<title>Describe the service | Service Studio</title>
</svelte:head>

<OnboardDetailsPage
	subject="service"
	backRoute="/onboard/service/method"
	actionRoute="/onboard/service/draft"
	caption="Start a new service, step 2 of 2"
	heading="Tell the assistant about the service"
	intro="It will use this, plus what is already on GOV.UK, to draft the journey and graph."
	initial={{
		name: 'Change driving licence address',
		description: "Change a user's driving licence address using either a postcode search or by entering the address manually.",
		link: 'https://www.gov.uk/change-address-driving-licence'
	}}
/>
