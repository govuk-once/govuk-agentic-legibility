<script lang="ts" module>
	// A step with a problem is one that has been reached but cannot be finished until something is put right.
	export type ReviewStepState = 'complete' | 'current' | 'problem' | 'upcoming';
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	/*
		One step of a review that is done in a few steps, such as the owner review. A bar of numbered steps shows how
		far along the review is, then the step's heading and a short explanation sit on the left with the work of the
		step on the right, and the buttons that move between steps sit in a bar along the bottom.
	*/

	interface Props {
		// Every step of the review, in order, with how far each one has got.
		steps: { label: string; state: ReviewStepState }[];
		heading: string;
		hint: string;
		// A short line under the explanation that says where the step stands, such as "Not saved yet".
		status?: Snippet;
		children: Snippet;
		actions: Snippet;
	}

	let { steps, heading, hint, status, children, actions }: Props = $props();

	// The words read out for each step, so a screen reader hears what the colour of its bar shows.
	const visuallyHiddenStates: Record<ReviewStepState, string> = {
		complete: 'complete',
		current: 'current step',
		problem: 'current step, has problems',
		upcoming: 'not started'
	};
</script>

<ol class="review-steps" aria-label="Review steps">
	{#each steps as step, index (step.label)}
		<li class="review-steps__step review-steps__step--{step.state}" aria-current={step.state === 'current' || step.state === 'problem' ? 'step' : undefined}>
			<span class="review-steps__number" aria-hidden="true">{index + 1}</span>
			<span class="govuk-visually-hidden">Step {index + 1} of {steps.length}, {step.label}: {visuallyHiddenStates[step.state]}</span>
			<span class="review-steps__bar"></span>
		</li>
	{/each}
</ol>

<div class="review-step govuk-grid-row">
	<div class="govuk-grid-column-one-third">
		<h2 class="govuk-heading-l govuk-!-margin-bottom-4">{heading}</h2>
		<p class="govuk-hint govuk-!-margin-bottom-4">{hint}</p>
		{@render status?.()}
	</div>
	<div class="govuk-grid-column-two-thirds">
		{@render children()}
	</div>
</div>

<div class="review-step__actions">
	<div class="govuk-button-group govuk-!-margin-bottom-0">
		{@render actions()}
	</div>
</div>

<style>
	/* The bar of steps runs the full width of the page between two rules, with the steps lined up under the heading. */
	.review-steps {
		display: flex;
		gap: 5px;
		margin: 20px 0 0;
		padding: 10px 40px;
		list-style: none;
		border-top: 1px solid #b1b4b6;
		border-bottom: 1px solid #b1b4b6;
	}

	.review-steps__step {
		display: flex;
		flex-direction: column;
		gap: 5px;
		width: 88px;
	}

	.review-steps__number {
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 1rem;
		line-height: 1.25;
		color: #505a5f;
	}

	.review-steps__bar {
		height: 6px;
		background-color: #b1b4b6;
	}

	.review-steps__step--complete .review-steps__number {
		font-weight: 700;
		color: #00703c;
	}

	.review-steps__step--complete .review-steps__bar {
		background-color: #00703c;
	}

	.review-steps__step--current .review-steps__number {
		font-weight: 700;
		color: #1d70b8;
	}

	.review-steps__step--current .review-steps__bar {
		background-color: #1d70b8;
	}

	.review-steps__step--problem .review-steps__number {
		font-weight: 700;
		color: #d4351c;
	}

	.review-steps__step--problem .review-steps__bar {
		background-color: #d4351c;
	}

	/* The grid row is pulled in by its own gutter, so the side padding is 25px to line the columns up at 40px. */
	.review-step {
		margin: 0;
		padding: 50px 25px;
	}

	.review-step__actions {
		padding: 20px 40px;
		background-color: #f3f2f1;
		border-top: 1px solid #b1b4b6;
	}

	/* A link for something that is not built yet is shown so the design is complete, but greyed out and not followed. */
	.review-step :global(.govuk-link[aria-disabled='true']),
	.review-step__actions :global(.govuk-link[aria-disabled='true']) {
		color: #505a5f;
		cursor: not-allowed;
	}

	@media (max-width: 640px) {
		.review-steps {
			padding-inline: 15px;
		}

		.review-step {
			padding: 30px 0;
		}

		.review-step__actions {
			padding: 15px;
		}
	}
</style>
