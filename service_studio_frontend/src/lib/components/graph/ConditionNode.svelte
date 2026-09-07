<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { ConditionNode } from '$lib/graph/types';

	let { data, selected }: NodeProps<ConditionNode> = $props();
</script>

<!-- Selection changes only the emphasis around the condition so the diamond meaning remains intact. -->
<div class:journey-condition-node--selected={selected} class="journey-condition-node">
	<!-- Hidden handles keep incoming and outgoing connections aligned with the points of the diamond. -->
	<Handle class="journey-node-handle" type="target" position={Position.Top} />
	<!-- SVG preserves the diamond border at every graph zoom level without rotating the question text. -->
	<svg
		class="journey-condition-node__shape"
		width="240"
		height="140"
		viewBox="0 0 240 140"
		xmlns="http://www.w3.org/2000/svg"
		aria-hidden="true"
	>
		<path d="M120 2 L238 70 L120 138 L2 70 Z" fill="#fff7bf" stroke="#0b0c0c" stroke-width="2" />
	</svg>
	<p class="journey-condition-node__question govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">
		{data.question}
	</p>
	<Handle class="journey-node-handle" type="source" position={Position.Bottom} />
</div>

<style>
	.journey-condition-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		width: 240px;
		height: 140px;
		color: #0b0c0c;
	}

	.journey-condition-node--selected {
		filter: drop-shadow(0 0 0 #1d70b8) drop-shadow(0 0 3px #1d70b8);
	}

	.journey-condition-node__shape {
		position: absolute;
		inset: 0;
	}

	.journey-condition-node__question {
		position: relative;
		width: 150px;
		text-align: center;
	}

	:global(.journey-node-handle) {
		width: 1px;
		height: 1px;
		opacity: 0;
		pointer-events: none;
	}
</style>
