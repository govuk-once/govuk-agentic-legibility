<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Pathname } from '$app/types';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	/*
		The page that shows what the assistant drafted: a message when nothing was generated, the problems when the
		draft did not match the required format, or the draft ready to open in an editor. The route works out the
		counts and says how the draft is held and opened, so the same page serves a service and a form.
	*/

	// What the form action of the route gave back. It is missing when the page is opened without submitting the details.
	export type DraftResult =
		| { success: true; name: string; warnings: string[] }
		| { success: false; issues: { path: string; message: string }[]; warnings: string[] }
		| null
		| undefined;

	interface Props {
		result: DraftResult;
		// What the draft is of, in one word, such as "service". It is used in the text.
		subject: string;
		// The route of the details page, which the back link and the links to try again lead to. This page resolves it.
		detailsRoute: Pathname;
		// How many steps and how many branches the draft has, counted the way the editor counts them.
		stepTotal: number;
		branchCount: number;
		// Holds the draft and opens it in the editor. It says whether it did. A false means the browser would not
		// hold the draft, so this page stays and tells the person why.
		onEdit: () => Promise<boolean>;
	}

	let { result, subject, detailsRoute, stepTotal, branchCount, onEdit }: Props = $props();

	// Set when the browser would not hold the draft, so the person is told why the editor did not open.
	let draftNotHeld = $state(false);

	async function handleEdit() {
		draftNotHeld = !(await onEdit());
	}
</script>

<ServiceHeader />

<main class="onboard-draft govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-draft__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve(detailsRoute)}>Back</a>

		{#if !result}
			<!-- Reached directly rather than by submitting the details form, so there is nothing to show. -->
			<h1 class="govuk-heading-xl">Nothing to show yet</h1>
			<p class="govuk-body">
				Go back to <a class="govuk-link" href={resolve(detailsRoute)}>the {subject} details</a> and submit the form to generate a first
				draft.
			</p>
		{:else if !result.success}
			<!-- Claude's response did not validate, even after one corrective turn, so the problems are shown
				directly rather than pretending a draft exists. -->
			<h1 class="govuk-heading-xl govuk-!-margin-bottom-5">The draft could not be generated</h1>
			<div class="govuk-error-summary" role="alert">
				<h2 class="govuk-error-summary__title">This did not match the required format</h2>
				<div class="govuk-error-summary__body">
					<ul class="govuk-list govuk-error-summary__list">
						{#each result.issues as issue, index (index)}
							<li>{issue.path}: {issue.message}</li>
						{/each}
					</ul>
				</div>
			</div>
			<p class="govuk-body">
				<a class="govuk-link" href={resolve(detailsRoute)}>Go back and try again</a>.
			</p>
		{:else}
			<p class="govuk-body-l">{result.name}</p>

			<!-- The icon and heading form one completion message while retaining a single page heading. -->
			<div class="onboard-draft__heading govuk-!-margin-bottom-4">
				<svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
					<circle cx="17" cy="17" r="17" fill="#00703c" />
					<path d="M9 17 L14.5 22.5 L25 11.5" fill="none" stroke="#ffffff" stroke-width="3" />
				</svg>
				<h1 class="govuk-heading-xl govuk-!-margin-bottom-0">Your first draft is ready</h1>
			</div>

			<p class="govuk-body-l govuk-!-margin-bottom-7">
				The assistant drafted {stepTotal} steps and {branchCount} branches from your {subject} brief. Open it in the editor to
				check the steps and change anything that is wrong.
			</p>

			{#if result.warnings.length > 0}
				<div class="govuk-warning-text govuk-!-margin-bottom-7">
					<span class="govuk-warning-text__icon" aria-hidden="true">!</span>
					<strong class="govuk-warning-text__text">
						<span class="govuk-visually-hidden">Warning</span>
						{#each result.warnings as warning, index (index)}
							<span class="onboard-draft__warning">{warning}</span>
						{/each}
					</strong>
				</div>
			{/if}

			{#if draftNotHeld}
				<div class="govuk-error-summary" role="alert">
					<h2 class="govuk-error-summary__title">The draft could not be opened</h2>
					<div class="govuk-error-summary__body">
						<p class="govuk-body">
							This browser would not keep the draft for the editor. Check that it allows site data and try again.
						</p>
					</div>
				</div>
			{/if}

			<div class="govuk-button-group">
				<button class="govuk-button" type="button" onclick={handleEdit}>Edit</button>
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

	@media (max-width: 40.0525em) {
		.onboard-draft {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}

		.onboard-draft__heading {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
