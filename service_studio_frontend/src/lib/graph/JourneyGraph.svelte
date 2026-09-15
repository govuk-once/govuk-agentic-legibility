<script lang="ts">
	import ConditionNode from './ConditionNode.svelte';
	import StepNode from './StepNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import { serviceToGraph } from './service-to-graph';
	import { layoutJourneyGraph, nodeSize } from './layout';
	import type { JourneyEdge, JourneyNode } from './types';
	import type { Service } from '$lib/schema';

	interface Props {
		service: Service;
		selectedStepId?: string | null;
	}

	let { service, selectedStepId = $bindable(null) }: Props = $props();

	// The graph is derived straight from the service in one chain, so there is no sync effect keeping a
	// separate copy of nodes and edges in step with it. serviceToGraph and layoutJourneyGraph are both
	// pure, so re-running them here on every change to the service is safe.
	const built = $derived(serviceToGraph(service));
	const laid = $derived(layoutJourneyGraph(built.nodes, built.edges));
	const nodes = $derived(laid.nodes);
	const edges = $derived(built.edges);
	const contentWidth = $derived(laid.width);
	const contentHeight = $derived(laid.height);
	const nodeById = $derived(new Map(nodes.map((node) => [node.id, node])));
	// Identifies the current set of nodes, so a fit is triggered when nodes are added, removed or a
	// different service is loaded, but not when a step's own text or size changes.
	const nodeSetKey = $derived(nodes.map((node) => node.id).join('|'));

	// The branch tag labels, positioned from the current node coordinates rather than stored, so they
	// follow the diamond and its outcome steps whenever the layout changes.
	const branchLabels = $derived(
		edges.flatMap((edge) => {
			if (edge.kind !== 'branch' || !edge.label) return [];
			const source = nodeById.get(edge.source);
			const target = nodeById.get(edge.target);
			if (!source || !target) return [];
			const from = anchorBottom(source);
			const to = anchorTop(target);
			return [
				{
					id: edge.id,
					label: edge.label,
					tagColour: edge.tagColour ?? 'grey',
					// Sit the label on the horizontal run of the edge, midway between the diamond and the
					// target. Each branch's horizontal run is at a different x, so the labels stay apart, and
					// the vertical midpoint keeps them clear of both the diamond and the step box below.
					x: (from.x + to.x) / 2,
					y: (from.y + to.y) / 2
				}
			];
		})
	);

	// Pan and zoom act on the viewport transform alone, so dragging or zooming the canvas never re-runs
	// the graph builder or layout.
	let panX = $state(0);
	let panY = $state(0);
	let zoom = $state(1);
	let isPanning = $state(false);
	// State so the fit effect re-runs once the canvas element is in the DOM.
	let canvasEl = $state<HTMLDivElement | undefined>(undefined);

	// The interactive zoom range is wider than the fit range: fitting deliberately stops at 0.9 so the
	// graph opens comfortably zoomed out in its narrow column, while a user can still zoom in to 1.5.
	const MIN_ZOOM = 0.25;
	const MAX_ZOOM = 1.5;
	const FIT_MAX_ZOOM = 0.9;
	const FIT_PADDING = 24;

	// The pointer position and pan offset captured when a drag starts, so each move is applied relative to
	// where the drag began rather than accumulating rounding errors frame by frame.
	let panStart: { x: number; y: number; panX: number; panY: number } | null = null;

	// Fits the graph into view once the canvas is in the DOM and the graph has a size, and again whenever
	// the set of nodes changes, so switching to a much larger or smaller service reframes it. It does not
	// fire on pan or zoom, or on an edit that leaves the node set the same, because it keys on
	// nodeSetKey, and applyFit writes only pan and zoom, which it does not read. The fit is run in a
	// later macrotask so the canvas is laid out at its CSS size first, and the key is latched only once
	// a fit actually lands, so a fit that measured too early is retried on the next change.
	let lastFitNodeSetKey = '';
	$effect(() => {
		if (!canvasEl || !contentWidth || !contentHeight || nodeSetKey === lastFitNodeSetKey) return;
		const key = nodeSetKey;
		setTimeout(() => {
			if (nodeSetKey === key && applyFit()) {
				lastFitNodeSetKey = key;
			}
		}, 0);
	});

	/**
	 * Returns the point at the bottom centre of a node, where an outgoing edge leaves it.
	 */
	function anchorBottom(node: JourneyNode): { x: number; y: number } {
		const { width, height } = nodeSize(node);
		return { x: node.position.x + width / 2, y: node.position.y + height };
	}

	/**
	 * Returns the point at the top centre of a node, where an incoming edge meets it.
	 */
	function anchorTop(node: JourneyNode): { x: number; y: number } {
		const { width } = nodeSize(node);
		return { x: node.position.x + width / 2, y: node.position.y };
	}

	/**
	 * Builds the SVG path for one edge. A straight line when source and target sit in the same column,
	 * otherwise a sharp orthogonal step that drops halfway, moves across, then drops into the target.
	 */
	function pathFor(edge: JourneyEdge): string {
		const source = nodeById.get(edge.source);
		const target = nodeById.get(edge.target);
		if (!source || !target) return '';

		const from = anchorBottom(source);
		const to = anchorTop(target);
		if (Math.abs(from.x - to.x) < 0.5) {
			return `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
		}
		const midY = (from.y + to.y) / 2;
		return `M ${from.x} ${from.y} L ${from.x} ${midY} L ${to.x} ${midY} L ${to.x} ${to.y}`;
	}

	/**
	 * Scales and centres the graph so the whole thing fits inside the canvas with a small margin. The
	 * canvas size is measured live from the element rather than read from a binding, so a fit still works
	 * when a resize has not yet propagated to reactive state. The new zoom is worked out from the fit
	 * scale alone, never from the current zoom, so repeated calls are stable.
	 */
	function applyFit(): boolean {
		if (!canvasEl || !contentWidth || !contentHeight) return false;

		const { width, height } = canvasEl.getBoundingClientRect();
		if (!width || !height) return false;

		const usableWidth = Math.max(1, width - FIT_PADDING * 2);
		const usableHeight = Math.max(1, height - FIT_PADDING * 2);
		const scale = Math.min(usableWidth / contentWidth, usableHeight / contentHeight, FIT_MAX_ZOOM);

		zoom = Math.max(MIN_ZOOM, scale);
		panX = (width - contentWidth * zoom) / 2;
		panY = (height - contentHeight * zoom) / 2;
		return true;
	}

	/**
	 * Wires pointer panning and wheel zooming onto the canvas element. Used as an attachment rather than
	 * markup event handlers so the wheel listener can be registered non-passive, which is what lets it
	 * call preventDefault to stop the page scrolling during a zoom.
	 */
	function panZoom(node: HTMLDivElement) {
		// Start a pan, unless the pointer went down on a node, in which case the event is left alone so the
		// node's own click still selects it.
		const onPointerDown = (event: PointerEvent) => {
			if (event.target instanceof Element && event.target.closest('.journey-graph__node')) return;
			panStart = { x: event.clientX, y: event.clientY, panX, panY };
			isPanning = true;
			node.setPointerCapture(event.pointerId);
		};

		// Move the viewport by the distance dragged since the pan started.
		const onPointerMove = (event: PointerEvent) => {
			if (!isPanning || !panStart) return;
			panX = panStart.panX + (event.clientX - panStart.x);
			panY = panStart.panY + (event.clientY - panStart.y);
		};

		// End the pan and release the captured pointer.
		const onPointerUp = (event: PointerEvent) => {
			if (!isPanning) return;
			isPanning = false;
			panStart = null;
			if (node.hasPointerCapture(event.pointerId)) {
				node.releasePointerCapture(event.pointerId);
			}
		};

		// Zoom toward the cursor, keeping the graph point under the pointer fixed while the scale changes.
		const onWheel = (event: WheelEvent) => {
			event.preventDefault();

			// Normalise the delta so a mouse reporting lines or pages zooms at a similar rate to one
			// reporting pixels.
			let delta = event.deltaY;
			if (event.deltaMode === 1) {
				delta *= 16;
			} else if (event.deltaMode === 2) {
				delta *= node.clientHeight;
			}

			const factor = Math.exp(-delta * 0.0015);
			const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));

			const rect = node.getBoundingClientRect();
			const cursorX = event.clientX - rect.left;
			const cursorY = event.clientY - rect.top;
			const graphX = (cursorX - panX) / zoom;
			const graphY = (cursorY - panY) / zoom;
			panX = cursorX - graphX * next;
			panY = cursorY - graphY * next;
			zoom = next;
		};

		node.addEventListener('pointerdown', onPointerDown);
		node.addEventListener('pointermove', onPointerMove);
		node.addEventListener('pointerup', onPointerUp);
		node.addEventListener('pointercancel', onPointerUp);
		node.addEventListener('wheel', onWheel, { passive: false });

		return () => {
			node.removeEventListener('pointerdown', onPointerDown);
			node.removeEventListener('pointermove', onPointerMove);
			node.removeEventListener('pointerup', onPointerUp);
			node.removeEventListener('pointercancel', onPointerUp);
			node.removeEventListener('wheel', onWheel);
		};
	}
</script>

<!-- The graph section gives its controls and viewport one accessible heading. -->
<section class="journey-graph" aria-labelledby="journey-graph-heading">
	<header class="journey-graph__header">
		<h2 id="journey-graph-heading" class="govuk-heading-m govuk-!-margin-bottom-0">Journey graph</h2>

		<!-- The control sits outside the viewport so moving the graph cannot move the action itself. -->
		<div class="journey-graph__controls">
			<button
				class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0"
				type="button"
				onclick={applyFit}
			>
				Fit to view
			</button>
		</div>
	</header>

	<!-- touch-action none stops the browser claiming a touch drag as a scroll gesture before the pointer
		handlers can treat it as a pan. -->
	<div
		class="journey-graph__canvas"
		class:journey-graph__canvas--panning={isPanning}
		bind:this={canvasEl}
		{@attach panZoom}
	>
		<div
			class="journey-graph__viewport"
			style:width="{contentWidth}px"
			style:height="{contentHeight}px"
			style:transform="translate({panX}px, {panY}px) scale({zoom})"
		>
			<svg class="journey-graph__edges" width={contentWidth} height={contentHeight} aria-hidden="true">
				<defs>
					<marker
						id="journey-arrowhead"
						viewBox="0 0 10 10"
						refX="9"
						refY="5"
						markerWidth="7"
						markerHeight="7"
						orient="auto"
					>
						<path d="M0 0 L10 5 L0 10 z" fill="#505a5f" />
					</marker>
				</defs>
				{#each edges as edge (edge.id)}
					<path class="journey-graph__edge" d={pathFor(edge)} marker-end="url(#journey-arrowhead)" />
				{/each}
			</svg>

			{#each nodes as node (node.id)}
				<div class="journey-graph__node" style:left="{node.position.x}px" style:top="{node.position.y}px">
					{#if node.type === 'step'}
						<StepNode
							data={node.data}
							selected={node.data.stepId === selectedStepId}
							onselect={() => (selectedStepId = node.data.stepId ?? null)}
							ariaLabel={node.ariaLabel}
						/>
					{:else if node.type === 'condition'}
						<ConditionNode data={node.data} />
					{:else}
						<TerminalNode data={node.data} />
					{/if}
				</div>
			{/each}

			{#each branchLabels as branchLabel (branchLabel.id)}
				<div
					class="journey-graph__edge-label"
					style:left="{branchLabel.x}px"
					style:top="{branchLabel.y}px"
				>
					<strong class="govuk-tag govuk-tag--{branchLabel.tagColour}">{branchLabel.label}</strong>
				</div>
			{/each}
		</div>
	</div>
</section>

<style>
	.journey-graph {
		display: flex;
		flex-direction: column;
		flex: 1 1 500px;
		min-width: 0;
		border: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-graph__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
		padding: 15px 20px;
		background-color: #f3f2f1;
		border-bottom: 1px solid #b1b4b6;
	}

	.journey-graph__controls {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 10px;
	}

	.journey-graph__canvas {
		position: relative;
		height: 750px;
		overflow: hidden;
		background-color: #ffffff;
		cursor: grab;
		touch-action: none;
	}

	.journey-graph__canvas--panning {
		cursor: grabbing;
	}

	.journey-graph__viewport {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
	}

	.journey-graph__edges {
		position: absolute;
		inset: 0;
		overflow: visible;
		pointer-events: none;
	}

	.journey-graph__edge {
		fill: none;
		stroke: #505a5f;
		stroke-width: 2;
	}

	.journey-graph__node {
		position: absolute;
	}

	.journey-graph__edge-label {
		position: absolute;
		transform: translate(-50%, -50%);
	}

	@media (max-width: 1100px) {
		.journey-graph {
			flex-basis: auto;
			width: 100%;
		}
	}

	@media (max-width: 640px) {
		.journey-graph__header {
			align-items: flex-start;
			flex-direction: column;
			padding: 15px;
		}

		.journey-graph__controls {
			align-items: flex-start;
			justify-content: flex-start;
			width: 100%;
		}

		.journey-graph__canvas {
			height: 550px;
		}
	}
</style>
