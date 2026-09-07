<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { StepNode } from '$lib/graph/types';

	let { data, selected }: NodeProps<StepNode> = $props();
</script>

<!-- Appearance states distinguish editing, selection and bypass without changing the step content. -->
<div
	class:journey-step-node--selected={selected}
	class:journey-step-node--editing={data.appearance === 'editing'}
	class:journey-step-node--bypassed={data.appearance === 'bypassed'}
	class="journey-step-node"
>
	<!-- Hidden handles provide fixed connection points without changing the approved node design. -->
	<Handle class="journey-node-handle" type="target" position={Position.Top} />
	<h3 class="govuk-heading-s govuk-!-margin-bottom-1">
		{#if data.stepNumber}{data.stepNumber}. {/if}{data.title}
	</h3>
	<p class="govuk-body-s govuk-!-margin-bottom-0">{data.description}</p>
	<Handle class="journey-node-handle" type="source" position={Position.Bottom} />
</div>

<style>
	.journey-step-node {
		box-sizing: border-box;
		width: 280px;
		height: 78px;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 2px solid #0b0c0c;
	}

	.journey-step-node--selected,
	.journey-step-node--editing {
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
