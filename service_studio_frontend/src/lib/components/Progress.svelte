<script lang="ts">
	import type { Stage } from './progress-stages';

	interface Props {
		stages: Stage[];
		// Set on the graph editor, whose own design embeds this sequence inside the shared banner row
		// rather than giving it a second full-width row of its own, so it needs to fit a 60px banner
		// rather than sit as a standalone section.
		compact?: boolean;
	}

	let { stages, compact = false }: Props = $props();

	// The words read out before each stage, so a screen reader hears what the marker shows.
	const visuallyHiddenStates: Record<Stage['state'], string> = {
		complete: 'Completed',
		current: 'Current step',
		upcoming: 'Upcoming step'
	};
</script>

<!-- The progress navigation communicates completed, current and upcoming prototype stages in one sequence. -->
<nav class="progress" class:progress--compact={compact} aria-label="Prototype stages">
	{#each stages as stage, index (stage.number)}
		{#if index > 0}
			<!-- Dividers separate neighbouring stages without adding another item to the sequence. -->
			<span class="progress__divider"></span>
		{/if}
		<!-- A complete stage with an address is a link back to it, and every other stage is text. -->
		<svelte:element
			this={stage.href ? 'a' : 'div'}
			href={stage.href}
			class={['progress__stage', stage.href && 'govuk-link progress__stage--link']}
			aria-current={stage.state === 'current' ? 'step' : undefined}
		>
			<span class="govuk-visually-hidden">
				{visuallyHiddenStates[stage.state]}:
			</span>
			{#if stage.state === 'complete'}
				<span class="progress__marker progress__marker--complete">
					<svg width="14" height="11" viewBox="0 0 14 11" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
						<path d="M1 5.5 L5 9.5 L13 1.5" fill="none" stroke="#ffffff" stroke-width="2.5" />
					</svg>
				</span>
			{:else}
				<span
					class="progress__marker"
					class:progress__marker--current={stage.state === 'current'}
				>
					<span class="progress__number">{stage.number}</span>
				</span>
			{/if}
			<span
				class="progress__label"
				class:progress__label--current={stage.state === 'current'}
			>
				{stage.label}
			</span>
		</svelte:element>
	{/each}
</nav>

<style>
	.progress {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		padding: 25px 40px 0;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.progress--compact {
		padding: 0;
		flex-wrap: nowrap;
	}

	.progress__stage {
		display: flex;
		align-items: center;
		gap: 10px;
		padding-inline: 20px;
	}

	.progress--compact .progress__stage {
		padding-inline: 15px;
	}

	.progress__stage:first-child {
		padding-left: 0;
	}

	.progress__divider {
		width: 1px;
		height: 28px;
		background-color: #b1b4b6;
	}

	.progress--compact .progress__divider {
		height: 22px;
	}

	/* The GOV.UK font leaves more room below its letters than above them. The text box of each number and each label
		is trimmed to the height of its capital letters, so the browser centres the letters themselves and not that
		extra room. A browser that does not support text-box yet centres the whole line. The number has a span of its
		own because only a block of text can be trimmed, and the marker round it is a flex box. */
	.progress__number,
	.progress__label {
		text-box: trim-both cap alphabetic;
	}

	.progress__marker {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 28px;
		height: 28px;
		border: 2px solid #b1b4b6;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.progress--compact .progress__marker {
		width: 24px;
		height: 24px;
	}

	.progress__marker--complete {
		background-color: #00703c;
		border: 0;
	}

	.progress__marker--current {
		background-color: #1d70b8;
		border: 0;
		color: #ffffff;
	}

	.progress__label {
		font-size: 1rem;
		line-height: 1.25;
		color: #505a5f;
	}

	.progress--compact .progress__label {
		white-space: nowrap;
	}

	/* A stage that links back shows its label in the link colour and underlined, as GOV.UK links are. */
	.progress__stage--link .progress__label {
		color: inherit;
		text-decoration: underline;
	}

	.progress__label--current {
		font-weight: 700;
		color: #0b0c0c;
	}

	@media (max-width: 640px) {
		.progress {
			align-items: flex-start;
			padding: 20px 15px 0;
		}

		.progress__stage {
			padding: 5px 10px;
		}

		.progress__stage:first-child {
			padding-left: 0;
		}
	}
</style>
