<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Pathname } from '$app/types';
	import type { Snippet } from 'svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import type { DraftLoad } from '$lib/draft-store';

	/*
		The page an editor shows in place of a draft it could not open: there was no draft in the browser tab, or the
		draft did not match the required format. Each editor gives the route where a new draft is started.
	*/

	interface Props {
		// Why the draft could not be opened, as the draft store gave it.
		problem: Extract<DraftLoad, { ok: false }>;
		// The route of the page where a new draft is started. This page resolves it.
		startRoute: Pathname;
		// What to say when there is nothing in the browser tab, for a page that is reached some other way than by
		// opening a new draft. Without it the page asks for a first draft.
		missing?: Snippet;
		// The browser tab title, for a page that is not opening a new draft.
		title?: string;
	}

	let { problem, startRoute, missing, title = 'Open the draft' }: Props = $props();
</script>

<svelte:head>
	<title>{title} | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="govuk-!-padding-top-9 govuk-!-padding-bottom-9 draft-problem">
	{#if problem.reason === 'missing' && missing}
		{@render missing()}
	{:else if problem.reason === 'missing'}
		<h1 class="govuk-heading-xl">Nothing to edit yet</h1>
		<p class="govuk-body">
			There is no draft in this browser tab. <a class="govuk-link" href={resolve(startRoute)}>Generate a first draft</a>
			and choose Edit to open it here.
		</p>
	{:else}
		<h1 class="govuk-heading-xl">The draft could not be opened</h1>
		<div class="govuk-error-summary" role="alert">
			<h2 class="govuk-error-summary__title">This did not match the required format</h2>
			<div class="govuk-error-summary__body">
				<ul class="govuk-list govuk-error-summary__list">
					{#each problem.issues as issue, index (index)}
						<li>{issue.path}: {issue.message}</li>
					{/each}
				</ul>
			</div>
		</div>
		<p class="govuk-body">
			<a class="govuk-link" href={resolve(startRoute)}>Generate a new draft</a>.
		</p>
	{/if}
</main>

<style>
	/* The left edge matches the Service Studio name, as on the onboarding pages. */
	.draft-problem {
		max-width: 700px;
		margin-left: 145px;
	}

	@media (max-width: 40.0525em) {
		.draft-problem {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}
	}
</style>
