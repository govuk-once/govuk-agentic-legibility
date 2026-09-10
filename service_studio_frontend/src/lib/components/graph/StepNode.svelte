<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { StepNode } from '$lib/graph/types';

	let { data, selected }: NodeProps<StepNode> = $props();
</script>

<!-- Selection is what shows a step is being edited, so the only other appearance this needs is bypassed.
	Width and height are set per node from its own content, computed alongside the rest of the graph,
	rather than every step sharing one fixed size regardless of how much text it has. -->
<div
	class:journey-step-node--selected={selected}
	class:journey-step-node--bypassed={data.appearance === 'bypassed'}
	class="journey-step-node"
	style:width="{data.width}px"
	style:height="{data.height}px"
>
	<!-- Hidden handles provide fixed connection points without changing the approved node design. -->
	<Handle class="journey-node-handle" type="target" position={Position.Top} />
	<h3 class="govuk-heading-s govuk-!-margin-bottom-1 journey-step-node__title">
		{#if data.stepNumber}{data.stepNumber}. {/if}{data.title}
	</h3>
	<p class="govuk-body-s govuk-!-margin-bottom-0 journey-step-node__description">{data.description}</p>
	<Handle class="journey-node-handle" type="source" position={Position.Bottom} />
</div>

<style>
	.journey-step-node {
		box-sizing: border-box;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 2px solid #0b0c0c;
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

	.journey-step-node--bypassed {
		border: 2px dashed #505a5f;
	}

	.journey-step-node--bypassed :global(.govuk-heading-s),
	.journey-step-node--bypassed :global(.govuk-body-s) {
		color: #505a5f;
	}

	:global(.journey-node-handle) {
		width: 1px;
		height: 1px;
		opacity: 0;
		pointer-events: none;
	}
</style>
