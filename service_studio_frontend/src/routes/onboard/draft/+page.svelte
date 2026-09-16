<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	const suggestedApiSteps = [
		{ step: '1: Choose entry method', api: 'choose_address_entry_method' },
		{ step: '2: Find address by postcode', api: 'find_address_by_postcode' },
		{ step: '3: Enter address manually', api: 'enter_address_manually' },
		{ step: '4: Confirm your new address', api: 'confirm_new_address' }
	];

	// A step with more than one route is a branch, the same rule service-to-graph.ts uses to
	// decide whether a step gets a decision diamond in the /edit graph.
	const branchCount = $derived(
		form?.success ? form.service.steps.filter((step) => step.transitions.length > 1).length : 0
	);

	/**
	 * Downloads the generated service as a JSON file, so it can be added to src/lib/examples by
	 * hand for now, until the editor is wired up to load a draft directly.
	 */
	function handleDownload() {
		if (!form?.success) return;

		const blob = new Blob([JSON.stringify(form.service, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = `${form.service.name || 'service'}.json`;
		link.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:head>
	<title>Review the first draft | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="onboard-draft govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-draft__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve('/onboard/details')}>Back</a>

		{#if !form}
			<!-- Reached directly rather than by submitting the details form, so there is nothing to show. -->
			<h1 class="govuk-heading-xl">Nothing to show yet</h1>
			<p class="govuk-body">
				Go back to <a class="govuk-link" href={resolve('/onboard/details')}>the service details</a> and submit the
				form to generate a first draft.
			</p>
		{:else if !form.success}
			<!-- Claude's response did not validate, even after one corrective turn, so the problems are shown
				directly rather than pretending a draft exists. -->
			<h1 class="govuk-heading-xl govuk-!-margin-bottom-5">The draft could not be generated</h1>
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This did not match the canonical schema</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each form.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
			<p class="govuk-body">
				<a class="govuk-link" href={resolve('/onboard/details')}>Go back and try again</a>.
			</p>
		{:else}
			<p class="govuk-body-l">{form.service.name}</p>

			<!-- The icon and heading form one completion message while retaining a single page heading. -->
			<div class="onboard-draft__heading govuk-!-margin-bottom-4">
				<svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
					<circle cx="17" cy="17" r="17" fill="#00703c" />
					<path d="M9 17 L14.5 22.5 L25 11.5" fill="none" stroke="#ffffff" stroke-width="3" />
				</svg>
				<h1 class="govuk-heading-xl govuk-!-margin-bottom-0">Your first draft is ready</h1>
			</div>

			<p class="govuk-body-l govuk-!-margin-bottom-7">
				The assistant drafted {form.service.steps.length} steps and {branchCount} branches from your service
				brief. Your canonical schema is ready to download.
			</p>

			{#if form.warnings.length > 0}
				<div class="govuk-warning-text govuk-!-margin-bottom-7">
					<span class="govuk-warning-text__icon" aria-hidden="true">!</span>
					<strong class="govuk-warning-text__text">
						<span class="govuk-visually-hidden">Warning</span>
						{#each form.warnings as warning, index (index)}
							<span class="onboard-draft__warning">{warning}</span>
						{/each}
					</strong>
				</div>
			{/if}

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

			<!-- Edit stays visually disabled until the editor is wired up to load a generated draft
				directly, downloading the schema and adding it to src/lib/examples by hand is the way to
				see it in /edit for now. -->
			<div class="govuk-button-group">
				<button class="govuk-button" type="button" disabled>Edit</button>
				<button class="govuk-button govuk-button--secondary" type="button" onclick={handleDownload}>
					Download schema
				</button>
			</div>
		{/if}
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

	.onboard-draft__warning {
		display: block;
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
