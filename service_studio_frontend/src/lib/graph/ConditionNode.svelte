<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { ConditionNode } from './types';

	let { data }: NodeProps<ConditionNode> = $props();
</script>

<!-- One shared source handle carries every branch route out of this gateway, dagre and
	reorderBranchSiblings decide how those routes fan out visually, the handle itself is just where they
	all leave from. -->
<Handle type="target" position={Position.Top}>
	<span class="journey-node-handle-hint" aria-hidden="true">+</span>
</Handle>

<!-- A plain diamond, no text: the route it stands for is named on the step that owns it and edited in
	the step editor's branch routes, so repeating that wording here only duplicated it. -->
<div class="journey-condition-node" role="img" aria-label={data.ariaLabel}>
	<div class="journey-condition-node__shape" class:journey-condition-node__shape--draft={data.draft}></div>
</div>

<Handle type="source" position={Position.Bottom}>
	<span class="journey-node-handle-hint" aria-hidden="true">+</span>
</Handle>

<style>
	.journey-condition-node {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: 40px;
	}

	.journey-condition-node__shape {
		box-sizing: border-box;
		width: 28px;
		height: 28px;
		background-color: #ffdd00;
		transform: rotate(45deg);
	}

	/* Its own colour at reduced opacity, plus a dashed outline, marks a shape placed from the toolbar but
		not yet wired to a step on both ends: it exists only on the canvas, not in the service, until that
		connection promotes it. Kept filled rather than hollow, so it stays as easy to spot as a real one. */
	.journey-condition-node__shape--draft {
		opacity: 0.55;
		border: 2px dashed #0b0c0c;
	}
</style>
