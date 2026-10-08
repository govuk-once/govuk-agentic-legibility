<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { TerminalNode } from './types';

	let { data }: NodeProps<TerminalNode> = $props();
</script>

<!-- Start only ever leads somewhere, End only ever receives, so each gets just the one handle its own
	role actually needs. -->
{#if data.appearance === 'start'}
	<Handle type="source" position={Position.Bottom}>
		<span class="journey-node-handle-hint" aria-hidden="true">+</span>
	</Handle>
{:else}
	<Handle type="target" position={Position.Top}>
		<span class="journey-node-handle-hint" aria-hidden="true">+</span>
	</Handle>
{/if}

<!-- Start and end share one component because their content is otherwise identical, differing only by
	the appearance modifier that sets the fill and, for the end event, the ring. The circle itself carries
	no text, matching the approved design, its label sits underneath instead. The label is positioned
	absolutely so it does not change the 40px circle the layout measures and edges anchor to. -->
<div class="journey-terminal-node" role="img" aria-label={data.ariaLabel}>
	<div
		class="journey-terminal-node__circle journey-terminal-node__circle--{data.appearance}"
		class:journey-terminal-node__circle--draft={data.draft}
	></div>
	<span class="journey-terminal-node__label">{data.label}</span>
</div>

<style>
	.journey-terminal-node {
		position: relative;
		box-sizing: border-box;
		width: 40px;
		height: 40px;
	}

	.journey-terminal-node__circle {
		box-sizing: border-box;
		width: 40px;
		height: 40px;
		border-radius: 50%;
	}

	.journey-terminal-node__circle--start {
		background-color: #0b0c0c;
	}

	.journey-terminal-node__circle--end {
		background-color: #00703c;
		border: 3px solid #0b0c0c;
	}

	/* Its own colour at reduced opacity, plus a dashed outline, marks a shape placed from the toolbar but
		not yet wired to a step: it exists only on the canvas, not in the service, until that one connection
		promotes it. Kept filled rather than hollow, so it stays as easy to spot as a real one. Comes after
		--start and --end so its dashed border wins over the end circle's own solid ring. */
	.journey-terminal-node__circle--draft {
		opacity: 0.55;
		border: 2px dashed #0b0c0c;
	}

	.journey-terminal-node__label {
		position: absolute;
		top: 46px;
		left: 50%;
		transform: translateX(-50%);
		font-family: 'GDS Transport', arial, sans-serif;
		font-size: 0.875rem;
		font-weight: 400;
		color: #505a5f;
		white-space: nowrap;
	}
</style>
