<script lang="ts">
	import { resolve } from '$app/paths';
	import Progress from '$lib/components/Progress.svelte';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	const stages = [
		{ number: 1, label: 'Start', state: 'current' as const },
		{ number: 2, label: 'Create', state: 'upcoming' as const },
		{ number: 3, label: 'Edit and review', state: 'upcoming' as const },
		{ number: 4, label: 'Policy check', state: 'upcoming' as const },
		{ number: 5, label: 'Publish', state: 'upcoming' as const }
	];

	const drafts = [
		{
			name: 'Renew your driving licence',
			detail: '6 steps · edited 2 hours ago',
			status: 'In policy review',
			statusColour: 'yellow'
		},
		{
			name: 'Book your theory test',
			detail: '5 steps · edited yesterday',
			status: 'Live',
			statusColour: 'green'
		},
		{
			name: 'Apply for a provisional licence',
			detail: '8 steps · edited last week',
			status: 'Draft',
			statusColour: 'grey'
		}
	];
</script>

<svelte:head>
	<title>Create a service | Service Studio</title>
</svelte:head>

<!-- The shared header and progress sequence place onboarding within the same Service Studio process as editing. -->
<ServiceHeader />
<Progress {stages} />

<main class="onboard-page govuk-!-padding-7">
	<h1 class="govuk-heading-xl">Create a service</h1>

	<!-- The primary action and supporting information remain side by side so users can understand the process before starting. -->
	<div class="onboard-page__content">
		<section class="onboard-start" aria-labelledby="onboard-start-heading">
			<div class="govuk-!-padding-5">
				<h2 id="onboard-start-heading" class="govuk-heading-m govuk-!-margin-bottom-2">Start a new service</h2>
				<p class="govuk-body govuk-!-margin-bottom-0">
					Create agentically legible service graphs that include steps and conditions.
				</p>
			</div>

			<!-- The lower panel separates the action from its explanation without introducing another card. -->
			<div class="onboard-start__action govuk-!-padding-5">
				<a class="govuk-button govuk-button--start" href={resolve('/onboard/method')}>
					Start a new service
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
				</a>
				<p class="govuk-body govuk-!-margin-bottom-0">
					Next you will choose whether the assistant drafts a first version for you, or you begin with a blank graph.
				</p>
			</div>
		</section>

		<div class="onboard-page__supporting-content">
			<!-- The summary sets expectations for automation, editing and policy review before any information is collected. -->
			<section class="onboard-explanation govuk-!-padding-left-6" aria-labelledby="onboard-explanation-heading">
				<h2 id="onboard-explanation-heading" class="govuk-heading-m">How it works</h2>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">A first draft is created</h3>
				<p class="govuk-body">
					A service graph including steps, questions and branching is drafted using a manual or automated process.
				</p>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">You edit the journey graph</h3>
				<p class="govuk-body">
					Reorder steps, change questions and adjust conditions visually.
				</p>

				<h3 class="govuk-heading-s govuk-!-margin-bottom-1">Policy signs it off</h3>
				<p class="govuk-body govuk-!-margin-bottom-0">
					Policy colleagues set what is required and authorise each step.
				</p>
			</section>

			<section aria-labelledby="drafts-heading">
				<h2 id="drafts-heading" class="govuk-heading-m govuk-!-margin-bottom-2">Your drafts</h2>

				<!-- Draft names look like the supplied design but remain text until draft navigation is agreed. -->
				<div class="onboard-drafts">
					{#each drafts as draft (draft.name)}
						<div class="onboard-drafts__item">
							<span class="govuk-link govuk-!-font-size-19 onboard-drafts__name">{draft.name}</span>
							<span class="govuk-body govuk-!-margin-bottom-0 onboard-drafts__detail">{draft.detail}</span>
							<strong class="govuk-tag govuk-tag--{draft.statusColour}">{draft.status}</strong>
						</div>
					{/each}
				</div>
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

	.onboard-start,
	.onboard-page__supporting-content {
		flex: 1 1 0;
		min-width: 0;
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

	.onboard-drafts__detail {
		flex: 0 0 260px;
		text-align: right;
	}

	.onboard-drafts__item :global(.govuk-tag) {
		flex-shrink: 0;
	}

	@media (max-width: 900px) {
		.onboard-page__content {
			flex-direction: column;
		}

		.onboard-start,
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
