<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	const suggestedApiSteps = [
		{ step: '1 · Choose entry method', api: 'choose_address_entry_method' },
		{ step: '2 · Find address by postcode', api: 'find_address_by_postcode' },
		{ step: '3 · Enter address manually', api: 'enter_address_manually' },
		{ step: '4 · Confirm your new address', api: 'confirm_new_address' }
	];
</script>

<svelte:head>
	<title>Review the first draft | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="onboard-draft govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-draft__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve('/onboard/details')}>Back</a>

		<p class="govuk-body-l">Change driving licence address</p>

		<!-- The icon and heading form one completion message while retaining a single page heading. -->
		<div class="onboard-draft__heading govuk-!-margin-bottom-4">
			<svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
				<circle cx="17" cy="17" r="17" fill="#00703c" />
				<path d="M9 17 L14.5 22.5 L25 11.5" fill="none" stroke="#ffffff" stroke-width="3" />
			</svg>
			<h1 class="govuk-heading-xl govuk-!-margin-bottom-0">Your first draft is ready</h1>
		</div>

		<p class="govuk-body-l govuk-!-margin-bottom-7">
			The assistant drafted 4 steps and 1 branch from your service brief. Your canonical schema is ready to download.
		</p>

		<section aria-labelledby="suggested-api-heading">
			<h2 id="suggested-api-heading" class="govuk-heading-m govuk-!-margin-bottom-2">Suggested API steps</h2>
			<p class="govuk-hint">API assignment is not available in this iteration.</p>

			<!-- Suggested mappings remain plain information so they do not imply that API assignment is available. -->
			<ul class="govuk-list suggested-api-steps govuk-!-margin-bottom-7">
				{#each suggestedApiSteps as suggestedStep (suggestedStep.step)}
					<li class="suggested-api-steps__item">
						<span class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{suggestedStep.step}</span>
						<span class="govuk-body govuk-!-margin-bottom-0">{suggestedStep.api}</span>
					</li>
				{/each}
			</ul>
		</section>

		<!-- The visual action reserves the final hierarchy without creating a provisional canonical file format. -->
		<button class="govuk-button" type="button">Download schema</button>
	</div>
</main>

<style>
	/* The left edge matches the Service Studio name so all onboarding stages use one visual column. */
	.onboard-draft {
		margin-left: 145px;
	}

	.onboard-draft__content {
		max-width: 700px;
	}

	.onboard-draft__heading {
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.onboard-draft__heading svg {
		flex-shrink: 0;
	}

	.suggested-api-steps {
		border-top: 1px solid #b1b4b6;
	}

	.suggested-api-steps__item {
		display: flex;
		align-items: center;
		gap: 30px;
		padding: 15px 20px;
		border-bottom: 1px solid #b1b4b6;
		background-color: #f3f2f1;
	}

	.suggested-api-steps__item > :first-child {
		flex: 0 0 260px;
	}

	@media (max-width: 40.0525em) {
		.onboard-draft {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}

		.onboard-draft__heading,
		.suggested-api-steps__item {
			align-items: flex-start;
			flex-direction: column;
		}

		.suggested-api-steps__item > :first-child {
			flex-basis: auto;
		}
	}
</style>
