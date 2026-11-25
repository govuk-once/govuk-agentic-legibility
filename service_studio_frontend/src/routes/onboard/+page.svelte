<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';
	import { startStages } from '$lib/components/progress-stages';
	import { draftStageTags, editedAgo } from '$lib/drafts/describe-draft';
	import { setOpenDraft, type DraftStage, type DraftSummary } from '$lib/drafts/draft-store';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The first page of each stage, so a draft opens where it was left.
	const stagePages = {
		Edit: '/edit-form/draft',
		'Owner review': '/owner-review/form',
		'Tech review': '/tech-review/form'
	} as const satisfies Record<DraftStage, string>;

	/**
	 * Opens a draft where it was left. The draft is marked as the one open in this browser tab first, because the
	 * page it opens on reads the draft from there.
	 */
	function openSavedDraft(event: MouseEvent, draft: DraftSummary) {
		event.preventDefault();
		setOpenDraft(draft.id);
		goto(resolve(stagePages[draft.stage]));
	}
</script>

<svelte:head>
	<title>Create a service | Service Studio</title>
</svelte:head>

<!-- One way to start something new. A start that cannot be used yet has no link, and its button is switched off. -->
{#snippet startOption(id: string, heading: string, intro: string, next: string, href?: string)}
	<section class="onboard-start" aria-labelledby="{id}-heading">
		<div class="govuk-!-padding-5">
			<h2 id="{id}-heading" class="govuk-heading-m govuk-!-margin-bottom-2">{heading}</h2>
			<p class="govuk-body govuk-!-margin-bottom-0">{intro}</p>
		</div>

		<!-- The lower panel separates the action from its explanation without introducing another card. -->
		<div class="onboard-start__action govuk-!-padding-5">
			{#if href}
				<a class="govuk-button govuk-button--start" {href}>
					{heading}
					{@render startIcon()}
				</a>
			{:else}
				<button class="govuk-button govuk-button--start" type="button" disabled>
					{heading}
					{@render startIcon()}
				</button>
			{/if}
			<p class="govuk-body govuk-!-margin-bottom-0">{next}</p>
		</div>
	</section>
{/snippet}

{#snippet startIcon()}
	<svg
		class="govuk-button__start-icon"
		xmlns="http://www.w3.org/2000/svg"
		width="17.5"
		height="19"
		viewBox="0 0 33 40"
		aria-hidden="true"
		focusable="false"
	>
		<path fill="currentColor" d="M0 0h13l20 20-20 20H0l20-20z" />
	</svg>
{/snippet}

<!-- The shared header and progress sequence place onboarding within the same Service Studio process as editing. -->
<ServiceHeader />
<Progress stages={startStages} />

<main class="onboard-page govuk-!-padding-7">
	<h1 class="govuk-heading-xl">Create a service</h1>

	<!-- The ways to start and the supporting information remain side by side so users can understand the process before starting. -->
	<div class="onboard-page__content">
		<div class="onboard-page__start-options">
			{@render startOption(
				'start-form',
				'Start a new form',
				'Create a digital form with steps, questions and conditions.',
				'Next you will choose how to draft it: with automation, from an existing GOV.UK form, or with a blank graph.',
				resolve('/onboard/form/method')
			)}
			{@render startOption(
				'start-service',
				'Start a new service',
				'Create agentically legible service graphs that include steps and conditions.',
				'Not available yet.'
			)}
		</div>

		<div class="onboard-page__supporting-content">
			<!-- The summary sets expectations for automation, editing and policy review before any information is collected. -->
			<section class="onboard-explanation govuk-!-padding-left-6" aria-labelledby="onboard-explanation-heading">
				<h2 id="onboard-explanation-heading" class="govuk-heading-m">How it works</h2>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">A first draft is created</h3>
				<p class="govuk-body">
					A service graph including steps, questions and branching is drafted using a manual or automated process.
				</p>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">You edit the journey graph</h3>
				<p class="govuk-body">Reorder steps, change questions and adjust conditions visually.</p>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">Policy signs it off</h3>
				<p class="govuk-body govuk-!-margin-bottom-0">Policy colleagues set what is required and authorise each step.</p>
			</section>

			<section aria-labelledby="drafts-heading">
				<h2 id="drafts-heading" class="govuk-heading-m govuk-!-margin-bottom-2">Your drafts</h2>

				{#if data.drafts.length === 0}
					<p class="govuk-body govuk-!-margin-bottom-0">You have no saved drafts. Choose Save draft in the editor to keep a form you are working on.</p>
				{:else}
					<div class="onboard-drafts">
						{#each data.drafts as draft (draft.id)}
							{@const tag = draftStageTags[draft.stage]}
							<div class="onboard-drafts__item">
								<a class="govuk-link govuk-!-font-size-19 onboard-drafts__name" href={resolve(stagePages[draft.stage])} onclick={(event) => openSavedDraft(event, draft)}>
									{draft.name}
								</a>
								<span class="govuk-body govuk-!-margin-bottom-0 onboard-drafts__detail">
									{draft.steps}
									{draft.steps === 1 ? 'step' : 'steps'}, {editedAgo(draft.savedAt, data.listedAt)}
								</span>
								<strong class="govuk-tag govuk-tag--{tag.colour}">{tag.label}</strong>
							</div>
						{/each}
					</div>
				{/if}
			</section>
		</div>
	</div>
</main>

<style>
	.onboard-page__content {
		display: flex;
		align-items: flex-start;
		gap: 50px;
	}

	.onboard-page__start-options,
	.onboard-page__supporting-content {
		flex: 1 1 0;
		min-width: 0;
	}

	.onboard-page__start-options {
		display: flex;
		flex-direction: column;
		gap: 25px;
	}

	.onboard-start {
		border: 1px solid #b1b4b6;
	}

	.onboard-start__action {
		border-top: 1px solid #b1b4b6;
	}

	.onboard-page__supporting-content {
		display: flex;
		flex-direction: column;
		gap: 40px;
	}

	.onboard-explanation {
		border-left: 5px solid #1d70b8;
	}

	.onboard-drafts {
		border-top: 1px solid #b1b4b6;
	}

	.onboard-drafts__item {
		display: flex;
		align-items: center;
		gap: 20px;
		padding: 15px 0;
		border-bottom: 1px solid #b1b4b6;
	}

	.onboard-drafts__name {
		flex: 1 1 auto;
	}

	/* The detail can get narrower and wrap on a narrow screen, so the tag after it stays inside the list. */
	.onboard-drafts__detail {
		flex: 0 1 260px;
		text-align: right;
	}

	.onboard-drafts__item :global(.govuk-tag) {
		flex-shrink: 0;
	}

	@media (max-width: 900px) {
		.onboard-page__content {
			flex-direction: column;
		}

		.onboard-page__start-options,
		.onboard-page__supporting-content {
			width: 100%;
		}
	}

	@media (max-width: 640px) {
		.onboard-drafts__item {
			align-items: flex-start;
			flex-direction: column;
			gap: 10px;
		}

		.onboard-drafts__detail {
			flex-basis: auto;
			text-align: left;
		}
	}
</style>
