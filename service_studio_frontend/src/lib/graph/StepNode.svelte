<script lang="ts">
	import type { StepNodeData } from './types';

	// selected shows the step is highlighted, whether that came from a click here or from the step list.
	// onselect reports a click back so the page can move the highlight, and ariaLabel names the button for
	// screen readers, since the node only shows the step title.
	let {
		data,
		selected,
		onselect,
		ariaLabel
	}: { data: StepNodeData; selected: boolean; onselect: () => void; ariaLabel: string } = $props();
</script>

<!-- A button, not a div, so the node is reachable by Tab and activates with Enter or Space without any
	extra key handling. The node shows the step title only. The description is left to the list beside the
	graph, so the graph stays compact. Width and height are set per node from the title, computed
	alongside the rest of the graph. -->
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
	<h3 class="govuk-heading-s govuk-!-margin-bottom-0 journey-step-node__title">
		{#if data.stepNumber}{data.stepNumber} &middot; {/if}{data.title}
	</h3>
</button>

<style>
	.journey-step-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		width: 100%;
		margin: 0;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
		text-align: left;
		cursor: pointer;
	}

	/* Extra rule for long titles, not the primary sizing mechanism: the computed height above already fits up to this
		many lines, so this only ever clips a title longer than that estimate expected. */
	.journey-step-node__title {
		overflow: hidden;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		line-clamp: 2;
		-webkit-line-clamp: 2;
	}

	.journey-step-node--selected {
		border: 2px solid #1d70b8;
	}

	.journey-step-node:focus-visible {
		outline: 4px solid #ffdd00;
		outline-offset: 2px;
	}
</style>
