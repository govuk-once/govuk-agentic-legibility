<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="stylesheet" href="/gov.css" />
	<link rel="stylesheet" href="/govuk-extras.css" />
</svelte:head>

<a href="#main-content" class="govuk-skip-link" data-module="govuk-skip-link">Skip to main content</a>

<header class="govuk-header" data-module="govuk-header">

</header>



{@render children()}

<footer class="govuk-footer">
	<div class="govuk-width-container">
	</div>
</footer>
