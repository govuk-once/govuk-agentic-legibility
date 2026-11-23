<script lang="ts">
	import type { Node, NodeProps } from '@xyflow/svelte';

	// The name of the module, written on the top edge of the border.
	let { data }: NodeProps<Node<{ label: string }>> = $props();
</script>

<!--
	A dotted border drawn behind the states of one copy of a module, with the module's name on its top edge, so a
	person can see which boxes came in together. It takes no pointer events, so a click or a drag inside it reaches
	the boxes or the canvas beneath.
-->
<div class="module-border-node">
	<span class="govuk-body-s govuk-!-margin-bottom-0 module-border-node__label">{data.label}</span>
</div>

<style>
	.module-border-node {
		position: relative;
		box-sizing: border-box;
		width: 100%;
		height: 100%;
		border: 1.5px dotted #9aa0a3;
		border-radius: 10px;
		pointer-events: none;
	}

	/* The name sits on the line, with the canvas colour behind it so the dots stop either side of it. */
	.module-border-node__label {
		position: absolute;
		top: -12px;
		left: 15px;
		padding-inline: 5px;
		color: #505a5f;
		background-color: #ffffff;
		white-space: nowrap;
	}
</style>
