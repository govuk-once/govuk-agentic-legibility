<script lang="ts">
	import { nodeSize } from './layout';
	import type { JourneyNode } from './types';

	interface Props {
		nodes: JourneyNode[];
		contentWidth: number;
		contentHeight: number;
		panX: number;
		panY: number;
		zoom: number;
		canvasWidth: number;
		canvasHeight: number;
		onpan: (panX: number, panY: number) => void;
	}

	let { nodes, contentWidth, contentHeight, panX, panY, zoom, canvasWidth, canvasHeight, onpan }: Props =
		$props();

	const MINIMAP_WIDTH = 100;
	const MINIMAP_HEIGHT = 72;

	// The scale that fits the whole graph into the minimap box, so the tiny overview always shows the
	// entire journey rather than a cropped slice of it.
	const scale = $derived(
		contentWidth && contentHeight
			? Math.min(MINIMAP_WIDTH / contentWidth, MINIMAP_HEIGHT / contentHeight)
			: 0
	);

	// Coloured to match what each shape means elsewhere on the canvas, rather than one flat swatch for
	// every node, so the overview reads as a miniature of the same journey rather than an abstract map.
	function colourFor(node: JourneyNode): string {
		if (node.type === 'condition') return '#ffdd00';
		if (node.type === 'terminal') return node.data.appearance === 'end' ? '#00703c' : '#0b0c0c';
		return '#b1b4b6';
	}

	const nodeRects = $derived(
		nodes.map((node) => {
			const { width, height } = nodeSize(node);
			return {
				id: node.id,
				x: node.position.x * scale,
				y: node.position.y * scale,
				width: Math.max(2, width * scale),
				height: Math.max(2, height * scale),
				colour: colourFor(node)
			};
		})
	);

	// The rectangle showing which part of the full graph the main canvas currently shows, derived from the
	// same pan and zoom the main canvas uses rather than a separate tracked value.
	const viewport = $derived({
		x: (-panX / zoom) * scale,
		y: (-panY / zoom) * scale,
		width: (canvasWidth / zoom) * scale,
		height: (canvasHeight / zoom) * scale
	});

	let dragging = $state(false);

	/**
	 * Recentres the main canvas on the point clicked or dragged to within the minimap, converting from
	 * minimap pixels back to the main canvas's own pan and zoom.
	 */
	function panToPoint(event: PointerEvent, target: HTMLElement) {
		const rect = target.getBoundingClientRect();
		const minimapX = event.clientX - rect.left;
		const minimapY = event.clientY - rect.top;
		if (!scale) return;

		const contentX = minimapX / scale;
		const contentY = minimapY / scale;
		onpan(canvasWidth / 2 - contentX * zoom, canvasHeight / 2 - contentY * zoom);
	}

	function onPointerDown(event: PointerEvent) {
		dragging = true;
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
		panToPoint(event, event.currentTarget as HTMLElement);
	}

	function onPointerMove(event: PointerEvent) {
		if (!dragging) return;
		panToPoint(event, event.currentTarget as HTMLElement);
	}

	function onPointerUp(event: PointerEvent) {
		dragging = false;
		const el = event.currentTarget as HTMLElement;
		if (el.hasPointerCapture(event.pointerId)) el.releasePointerCapture(event.pointerId);
	}
</script>

<!-- A scaled overview of the whole graph with the main canvas's current view marked on it, so panning a
	long journey does not mean losing track of where the visible part sits in the whole. -->
<div
	class="graph-minimap"
	role="img"
	aria-label="Overview of the journey graph"
	onpointerdown={onPointerDown}
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
	onpointercancel={onPointerUp}
>
	{#each nodeRects as rect (rect.id)}
		<div
			class="graph-minimap__node"
			style:left="{rect.x}px"
			style:top="{rect.y}px"
			style:width="{rect.width}px"
			style:height="{rect.height}px"
			style:background-color={rect.colour}
		></div>
	{/each}
	<div
		class="graph-minimap__viewport"
		style:left="{viewport.x}px"
		style:top="{viewport.y}px"
		style:width="{viewport.width}px"
		style:height="{viewport.height}px"
	></div>
</div>

<style>
	.graph-minimap {
		position: relative;
		width: 100px;
		height: 72px;
		flex-shrink: 0;
		overflow: hidden;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		cursor: pointer;
		touch-action: none;
	}

	.graph-minimap__node {
		position: absolute;
	}

	.graph-minimap__viewport {
		position: absolute;
		box-sizing: border-box;
		border: 1.5px solid #1d70b8;
		pointer-events: none;
	}
</style>
