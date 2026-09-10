<script lang="ts">
	import ConditionNode from './ConditionNode.svelte';
	import StepNode from './StepNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import { createJourneyGraph } from './build-journey-graph';
	import { layoutJourneyGraph, nodeSize } from './layout';
	import { addressChangeBranchDecoration } from './branch-decoration';
	import type { JourneyEdge, JourneyNode } from './types';
	import type { JourneyStep } from '$lib/journey/types';

	interface Props {
		steps: JourneyStep[];
		selectedStepId?: string | null;
	}

	let { steps, selectedStepId = $bindable(null) }: Props = $props();

	// The one interactive control that changes the graph structure. It starts on so the branch is visible
	// without a click first.
	let showBranching = $state(true);

	// The graph is derived straight from its inputs in one chain, so there is no sync effect keeping a
	// separate copy of nodes and edges in step with the source. layoutJourneyGraph is pure, so re-running
	// it here on every steps or toggle change is safe.
	const built = $derived(createJourneyGraph(steps, showBranching, addressChangeBranchDecoration));
	const laid = $derived(layoutJourneyGraph(built.nodes, built.edges));
	const nodes = $derived(laid.nodes);
	const edges = $derived(built.edges);
	const contentWidth = $derived(laid.width);
	const contentHeight = $derived(laid.height);
	const nodeById = $derived(new Map(nodes.map((node) => [node.id, node])));

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
					// Bias the label toward the diamond, the conventional spot for a decision outcome label.
					x: (from.x + to.x) / 2,
					y: from.y + (to.y - from.y) * 0.4
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
	let canvasWidth = $state(0);
	let canvasHeight = $state(0);
	let canvasEl: HTMLDivElement | undefined;

	// The interactive zoom range is wider than the fit range: fitting deliberately stops at 0.9 so the
	// graph opens comfortably zoomed out in its narrow column, while a user can still zoom in to 1.5.
	const MIN_ZOOM = 0.25;
	const MAX_ZOOM = 1.5;
	const FIT_MAX_ZOOM = 0.9;
	const FIT_PADDING = 24;

	// The pointer position and pan offset captured when a drag starts, so each move is applied relative to
	// where the drag began rather than accumulating rounding errors frame by frame.
	let panStart: { x: number; y: number; panX: number; panY: number } | null = null;

	// Runs once, the first time the canvas and the graph both have a measured size, to fit the graph into
	// view on load. Latched by a plain variable so it never fires again on a later rebuild, and it reads
	// no pan or zoom state so applyFit writing those cannot re-trigger it.
	let hasFitted = false;
	$effect(() => {
		if (hasFitted) return;
		if (canvasWidth && canvasHeight && contentWidth && contentHeight) {
			hasFitted = true;
			applyFit();
		}
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
	 * Scales and centres the graph so the whole thing fits inside the canvas with a small margin. Works
	 * out the new zoom from the fit scale alone, never from the current zoom, so repeated calls are stable.
	 */
	function applyFit() {
		if (!canvasWidth || !canvasHeight || !contentWidth || !contentHeight) return;

		const usableWidth = Math.max(1, canvasWidth - FIT_PADDING * 2);
		const usableHeight = Math.max(1, canvasHeight - FIT_PADDING * 2);
		const scale = Math.min(usableWidth / contentWidth, usableHeight / contentHeight, FIT_MAX_ZOOM);

		zoom = Math.max(MIN_ZOOM, scale);
		panX = (canvasWidth - contentWidth * zoom) / 2;
		panY = (canvasHeight - contentHeight * zoom) / 2;
	}

	/**
	 * Wires pointer panning and wheel zooming onto the canvas element. Used as an attachment rather than
	 * markup event handlers so the wheel listener can be registered non-passive, which is what lets it
	 * call preventDefault to stop the page scrolling during a zoom, and so the element reference the fit
	 * and zoom maths need is captured without a separate binding.
	 */
	function panZoom(node: HTMLDivElement) {
		canvasEl = node;

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
				delta *= canvasHeight;
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

		<!-- Controls sit outside the viewport so moving the graph cannot move the actions themselves. -->
		<div class="journey-graph__controls">
			<div class="govuk-checkboxes govuk-checkboxes--small">
				<div class="govuk-checkboxes__item">
					<input
						class="govuk-checkboxes__input"
						id="show-branching"
						type="checkbox"
						bind:checked={showBranching}
						onchange={applyFit}
					/>
					<label class="govuk-label govuk-checkboxes__label" for="show-branching">Show branching</label>
				</div>
			</div>

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
		bind:clientWidth={canvasWidth}
		bind:clientHeight={canvasHeight}
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
