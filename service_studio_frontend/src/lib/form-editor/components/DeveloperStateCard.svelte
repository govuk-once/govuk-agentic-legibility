<script lang="ts">
	import type { StateFact } from '$lib/process-graph/describe-state';

	interface Props {
		title: string;
		// The label and colour of the tag for this kind of state, the same as it has anywhere else in the editor.
		tagLabel: string;
		tagColour: string;
		// What the state does, as lines of words. Nothing here can be changed.
		facts: StateFact[];
		onClose: () => void;
	}

	let { title, tagLabel, tagColour, facts, onClose }: Props = $props();
</script>

<!-- A state that a developer sets up is shown with its values as words, so a person can see what it does without
	being able to break it. -->
<div class="developer-state-card" role="group" aria-label="{title}, set up by a developer">
	<div class="developer-state-card__header">
		<div class="developer-state-card__summary">
			<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{title}</h3>
			<strong class="govuk-tag govuk-tag--{tagColour}">{tagLabel}</strong>
		</div>
		<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={onClose}>Close</button>
	</div>

	<div class="developer-state-card__body">
		<div class="govuk-inset-text govuk-!-margin-top-0 govuk-!-margin-bottom-0">
			A developer sets up this step at the technical review.
		</div>

		{#if facts.length > 0}
			<dl class="developer-state-card__facts">
				{#each facts as fact, index (index)}
					<div>
						<dt class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">{fact.label}</dt>
						<dd class="govuk-body govuk-!-margin-bottom-0 developer-state-card__value">{fact.value}</dd>
					</div>
				{/each}
			</dl>
		{/if}
	</div>
</div>

<style>
	.developer-state-card {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-height: 0;
		background-color: #ffffff;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.developer-state-card__header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 10px;
		padding: 18px 16px 14px;
		border-bottom: 1px solid #b1b4b6;
	}

	.developer-state-card__summary {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
		min-width: 0;
	}

	.developer-state-card__body {
		flex: 1 1 auto;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 16px;
	}

	.developer-state-card__facts {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
	}

	/* A long value wraps inside the panel and does not push it wider. */
	.developer-state-card__value {
		margin-left: 0;
		overflow-wrap: anywhere;
	}
</style>
