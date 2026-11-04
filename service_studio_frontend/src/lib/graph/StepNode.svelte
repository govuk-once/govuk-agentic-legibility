<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { ProcessStepNode } from './process-graph-types';

	// selected is set by the graph that holds this node, so a click on the node and a choice in the list
	// of states highlight it in the same way. What a click means is decided in one place, the graph's
	// onnodeclick, and not inside this component.
	let { data, selected }: NodeProps<ProcessStepNode> = $props();
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
	class:journey-step-node--opens-process={data.opensProcess}
	role="button"
	tabindex="-1"
	aria-pressed={selected}
	aria-label={data.ariaLabel}
>
	<h3 class="govuk-heading-s govuk-!-margin-bottom-0 journey-step-node__title">
		{#if data.stepNumber}{data.stepNumber} &middot; {/if}{data.title}
	</h3>
	{#if data.opensProcess}
		<!-- Clicking anywhere on the box opens the process, so this line only tells the person which one. -->
		<p class="govuk-body govuk-!-margin-bottom-0 journey-step-node__action">Open {data.opensProcess.title}</p>
	{/if}
</div>

<Handle type="source" position={Position.Bottom}>
	<span class="journey-node-handle-hint" aria-hidden="true">+</span>
</Handle>

<style>
	.journey-step-node {
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		justify-content: center;
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

	/* A box that opens another process looks like a link, so it is clear it can be clicked. */
	.journey-step-node--opens-process {
		cursor: pointer;
	}

	.journey-step-node__action {
		color: #1d70b8;
		text-decoration: underline;
	}

	.journey-step-node--selected {
		border: 2px solid #1d70b8;
	}
</style>
