<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { TerminalNode } from '$lib/graph/types';

	let { data, selected }: NodeProps<TerminalNode> = $props();
</script>

<!-- Start and end share one component because their content and selection behaviour are otherwise identical. -->
<div
	class:journey-terminal-node--end={data.appearance === 'end'}
	class:journey-terminal-node--selected={selected}
	class="journey-terminal-node govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0"
>
	<!-- Terminal nodes expose only the connection direction allowed by their place at the start or end of the journey. -->
	{#if data.appearance === 'end'}
		<Handle class="journey-node-handle" type="target" position={Position.Top} />
	{/if}
	{data.label}
	{#if data.appearance === 'start'}
		<Handle class="journey-node-handle" type="source" position={Position.Bottom} />
	{/if}
</div>

<style>
	.journey-terminal-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 112px;
		height: 42px;
		padding: 10px 20px;
		background-color: #0b0c0c;
		color: #ffffff;
	}

	.journey-terminal-node--end {
		background-color: #00703c;
	}

	.journey-terminal-node--selected {
		outline: 4px solid #1d70b8;
		outline-offset: 2px;
	}

	:global(.journey-node-handle) {
		width: 1px;
		height: 1px;
		opacity: 0;
		pointer-events: none;
	}
</style>
