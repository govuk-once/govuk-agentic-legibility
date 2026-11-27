<script lang="ts">
	import type { Node, NodeProps } from '@xyflow/svelte';
	import type { ModuleBorderData } from '$lib/modules/module-borders';

	let { data }: NodeProps<Node<ModuleBorderData>> = $props();
</script>

<!--
	A dotted border drawn behind the states of one copy of a module, with the module's name on its top edge, so a
	person can see which boxes came in together. Only the move symbol beside the name takes the pointer, and dragging
	it moves the whole module. It is a four way arrow and not a dot, because a dot on a box is where a line is drawn
	from. A click or a drag anywhere else inside the border reaches the boxes or the canvas beneath.
-->
<div class="module-border-node">
	<span class="module-border-node__name">
		<!-- The class is the one moduleBorderHandleClass names, which tells Svelte Flow this is the only place to drag from. -->
		<span class="module-border-node__handle" title="Drag to move the whole module" aria-hidden="true">
			<svg
				width="18"
				height="18"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				focusable="false"
			>
				<path d="M12 3v18M3 12h18" />
				<path d="M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3" />
			</svg>
		</span>
		<span class="govuk-body-s govuk-!-margin-bottom-0 module-border-node__label secondary-text">{data.label}</span>
	</span>
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

	/* The move symbol and the name sit on the line, with the canvas colour behind them so the dots stop either side. */
	.module-border-node__name {
		position: absolute;
		top: -12px;
		left: 15px;
		display: flex;
		align-items: center;
		gap: 5px;
		padding-inline: 5px;
		background-color: #ffffff;
	}

	.module-border-node__label {
		white-space: nowrap;
	}

	/* The only part of the border that takes the pointer. It darkens when pointed at, so it is clear it can be moved. */
	.module-border-node__handle {
		display: flex;
		color: #505a5f;
		cursor: grab;
		pointer-events: auto;
	}

	.module-border-node__handle:hover {
		color: #0b0c0c;
	}
</style>
