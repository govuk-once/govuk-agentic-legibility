<script lang="ts">
	import type { StepNodeData } from './types';

	// selected shows the step is highlighted, whether that came from a click here or from the step list.
	// onselect reports a click back so the page can move the highlight, and ariaLabel names the button for
	// screen readers since its visible text is split across a heading and a paragraph.
	let {
		data,
		selected,
		onselect,
		ariaLabel
	}: { data: StepNodeData; selected: boolean; onselect: () => void; ariaLabel: string } = $props();
</script>

<!-- A button, not a div, so the node is reachable by Tab and activates with Enter or Space without any
	extra key handling. Width and height are set per node from its own content, computed alongside the rest
	of the graph, rather than every step sharing one fixed size regardless of how much text it has. -->
<button
	type="button"
	class="journey-step-node"
	class:journey-step-node--selected={selected}
	aria-pressed={selected}
	aria-label={ariaLabel}
	style:width="{data.width}px"
	style:height="{data.height}px"
	onclick={onselect}
>
	<h3 class="govuk-heading-s govuk-!-margin-bottom-1 journey-step-node__title">
		{#if data.stepNumber}{data.stepNumber}. {/if}{data.title}
	</h3>
	<p class="govuk-body-s govuk-!-margin-bottom-0 journey-step-node__description">{data.description}</p>
</button>

<style>
	.journey-step-node {
		box-sizing: border-box;
		display: block;
		width: 100%;
		margin: 0;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 2px solid #0b0c0c;
		font-family: 'GDS Transport', arial, sans-serif;
		text-align: left;
		cursor: pointer;
	}

	/* A safety net, not the primary sizing mechanism: the computed height above already fits up to this
		many lines, so this only ever clips content that is longer than that estimate expected. */
	.journey-step-node__title,
	.journey-step-node__description {
		overflow: hidden;
		display: -webkit-box;
		-webkit-box-orient: vertical;
	}

	.journey-step-node__title {
		line-clamp: 2;
		-webkit-line-clamp: 2;
	}

	.journey-step-node__description {
		line-clamp: 2;
		-webkit-line-clamp: 2;
	}

	.journey-step-node--selected {
		background-color: #e8f1f8;
		border: 3px solid #1d70b8;
	}

	.journey-step-node:focus-visible {
		outline: 4px solid #ffdd00;
		outline-offset: 2px;
	}
</style>
