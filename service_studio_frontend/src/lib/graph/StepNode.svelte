<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { StepNode } from './types';

	// selected comes from Svelte Flow's own selection state now, driven by clicking the node; opening the
	// step editor is handled centrally in JourneyGraph.svelte's onnodeclick, not from inside this
	// component, so the same one place decides what a click on any node type means.
	let { data, selected }: NodeProps<StepNode> = $props();
</script>

<!-- Handles sit top and bottom only: target on top, source on bottom, in the strict pairing Svelte Flow
	defaults to, so a drag always resolves onto the correct side regardless of which step sits above the
	other, including a loop back to an earlier step. The "+" hints at the connection a drag from here
	starts, not a click target of its own. -->
<Handle type="target" position={Position.Top}>
	<span class="journey-node-handle-hint" aria-hidden="true">+</span>
</Handle>

<!-- The node shows the step title only. The description is left to the list beside the graph, so the
	graph stays compact. Width and height are set per node from the title, computed alongside the rest of
	the graph. -->
<div
	class="journey-step-node"
	class:journey-step-node--selected={selected}
	role="button"
	tabindex="-1"
	aria-pressed={selected}
	aria-label={data.ariaLabel}
>
	<h3 class="govuk-heading-s govuk-!-margin-bottom-0 journey-step-node__title">
		{#if data.stepNumber}{data.stepNumber} &middot; {/if}{data.title}
	</h3>
</div>

<Handle type="source" position={Position.Bottom}>
	<span class="journey-node-handle-hint" aria-hidden="true">+</span>
</Handle>

<style>
	.journey-step-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		width: 100%;
		height: 100%;
		margin: 0;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
		text-align: left;
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
</style>
