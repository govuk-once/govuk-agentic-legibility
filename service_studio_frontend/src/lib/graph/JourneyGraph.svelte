<script lang="ts">
	import ConditionNode from './ConditionNode.svelte';
	import StepNode from './StepNode.svelte';
	import TerminalNode from './TerminalNode.svelte';
	import GraphMinimap from './GraphMinimap.svelte';
	import { serviceToGraph } from './service-to-graph';
	import { layoutJourneyGraph, nodeSize } from './layout';
	import type { JourneyEdge, JourneyNode } from './types';
	import type { Service } from '$lib/schema';

	interface Props {
		service: Service;
		selectedStepId?: string | null;
		// Both live here as bindable rather than owned by the page, because they drive the pan/zoom
		// transform and the display-only service filter this component already computes. The page's own
		// toolbar, which sits above this component and the rest of the editor body, reads and writes them
		// the same way it does selectedStepId.
		showBranching?: boolean;
		zoom?: number;
		// Reports a step node click without deciding what it means: with no tool armed the page just
		// selects the step, with one armed it applies that tool to the step instead. Falls back to
		// self-managed selection when not provided, so the component still works used on its own.
		onNodeActivate?: (stepId: string) => void;
		// Fired from the "+" that appears on any route out of a step, including each of a branch step's
		// own routes, with the step that route belongs to and the specific target it currently leads to,
		// or null for a step's own dead end, which has no target to name.
		onInsertAfter?: (stepId: string, targetStepId: string | null) => void;
	}

	let {
		service,
		selectedStepId = $bindable(null),
		showBranching = $bindable(true),
		zoom = $bindable(1),
		onNodeActivate,
		onInsertAfter
	}: Props = $props();

	// Off, every branching step is shown with only its first route, collapsing the rest of that branch out
	// of the picture. This never touches the real service, only what is built and laid out for display.
	const displayService = $derived(
		showBranching
			? service
			: {
					...service,
					steps: service.steps.map((step) =>
						step.transitions.length > 1 ? { ...step, transitions: step.transitions.slice(0, 1) } : step
					)
				}
	);

	// The graph is derived straight from the service in one chain, so there is no sync effect keeping a
	// separate copy of nodes and edges in step with it. serviceToGraph and layoutJourneyGraph are both
	// pure, so re-running them here on every change to the service is safe.
	const built = $derived(serviceToGraph(displayService));
	const laid = $derived(layoutJourneyGraph(built.nodes, built.edges));
	const nodes = $derived(laid.nodes);
	const edges = $derived(built.edges);
	const contentWidth = $derived(laid.width);
	const contentHeight = $derived(laid.height);
	const nodeById = $derived(new Map(nodes.map((node) => [node.id, node])));
	// Identifies the current set of nodes, so a fit is triggered when nodes are added, removed or a
	// different service is loaded, but not when a step's own text or size changes.
	const nodeSetKey = $derived(nodes.map((node) => node.id).join('|'));

	// Maps a gateway node's own id to the step that owns it, the source of the sequence edge leading into
	// it, so a branch edge, whose own source is the gateway rather than a step, can still be traced back
	// to the step whose transitions actually hold that route.
	const gatewayOwner = $derived(
		new Map(
			edges
				.filter((edge) => edge.kind === 'sequence' && nodeById.get(edge.target)?.type === 'condition')
				.map((edge) => [edge.target, edge.source])
		)
	);

	// Where the append "+" appears: the midpoint of every sequence edge that leaves a step with no onward
	// route yet, and every branch edge leaving a gateway, one per route a branch step has, not just its
	// first. It also appears on the one edge leaving the start terminal, so a step can be inserted before
	// the current first step, reported with the sentinel id 'start' since there is no real step to key it
	// by. Each point carries the exact target its own route currently leads to, null for a dead end,
	// which has no target to name, so the handler can tell a branch step's routes apart by target rather
	// than assuming there is only ever one.
	const insertPoints = $derived(
		edges.flatMap((edge) => {
			const source = nodeById.get(edge.source);
			const target = nodeById.get(edge.target);
			if (!source || !target || target.type === 'condition') return [];

			let stepId: string | undefined;
			if (edge.kind === 'sequence' && source.type === 'step') {
				stepId = source.data.stepId;
			} else if (edge.kind === 'sequence' && source.type === 'terminal' && source.data.appearance === 'start') {
				stepId = 'start';
			} else if (edge.kind === 'branch' && source.type === 'condition') {
				stepId = gatewayOwner.get(source.id);
			}
			if (!stepId) return [];

			// A step type target names the route explicitly; a terminal target is a dead end, which has no
			// step to name, so null stands for "this step's own dead end" instead.
			const targetStepId = target.type === 'step' ? (target.data.stepId ?? null) : null;

			const from = anchorBottom(source);
			const to = anchorTop(target);
			return [
				{ id: edge.id, stepId, targetStepId, x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 }
			];
		})
	);

	// Pan and zoom act on the viewport transform alone, so dragging or zooming the canvas never re-runs
	// the graph builder or layout.
	let panX = $state(0);
	let panY = $state(0);
	let isPanning = $state(false);
	// State so the fit effect re-runs once the canvas element is in the DOM.
	let canvasEl = $state<HTMLDivElement | undefined>(undefined);
	// Tracked with a ResizeObserver, rather than read once, because the canvas now fills whatever space
	// its full page layout gives it instead of a fixed height, so its size can genuinely change.
	let canvasWidth = $state(0);
	let canvasHeight = $state(0);

	// The interactive zoom range is wider than the fit range: fitting deliberately stops at 0.9 so the
	// graph opens comfortably zoomed out, while a user can still zoom in to 1.5.
	const MIN_ZOOM = 0.25;
	const MAX_ZOOM = 1.5;
	const FIT_MAX_ZOOM = 0.9;
	const FIT_PADDING = 24;
	const ZOOM_STEP = 0.1;

	// The pointer position and pan offset captured when a drag starts, so each move is applied relative to
	// where the drag began rather than accumulating rounding errors frame by frame.
	let panStart: { x: number; y: number; panX: number; panY: number } | null = null;

	$effect(() => {
		if (!canvasEl) return;
		const observer = new ResizeObserver((entries) => {
			const entry = entries[0];
			if (!entry) return;
			canvasWidth = entry.contentRect.width;
			canvasHeight = entry.contentRect.height;
		});
		observer.observe(canvasEl);
		return () => observer.disconnect();
	});

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

	// Exposed so the page's own toolbar, which sits above this component, can trigger a fit and step the
	// zoom the same way its in-canvas controls used to, via bind:this rather than duplicating this math.
	export function fit() {
		applyFit();
	}

	export function zoomIn() {
		adjustZoom(ZOOM_STEP);
	}

	export function zoomOut() {
		adjustZoom(-ZOOM_STEP);
	}

	/**
	 * Steps the zoom level from a button press, keeping the canvas's own centre point fixed in the graph
	 * rather than the top left, since a button press has no cursor position to anchor the zoom to the way
	 * the wheel handler below does.
	 */
	function adjustZoom(delta: number) {
		if (!canvasEl) return;
		const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom + delta));
		const centreX = canvasEl.clientWidth / 2;
		const centreY = canvasEl.clientHeight / 2;
		const graphX = (centreX - panX) / zoom;
		const graphY = (centreY - panY) / zoom;
		panX = centreX - graphX * next;
		panY = centreY - graphY * next;
		zoom = next;
	}

	/**
	 * Wires pointer panning and wheel zooming onto the canvas element. Used as an attachment rather than
	 * markup event handlers so the wheel listener can be registered non-passive, which is what lets it
	 * call preventDefault to stop the page scrolling during a zoom.
	 */
	function panZoom(node: HTMLDivElement) {
		// Start a pan, unless the pointer went down on a node or the append "+", in which case the event is
		// left alone so the element's own click still fires: capturing the pointer for a pan here would
		// otherwise swallow the click these overlay buttons depend on.
		const onPointerDown = (event: PointerEvent) => {
			if (
				event.target instanceof Element &&
				event.target.closest('.journey-graph__node, .journey-graph__insert')
			) {
				return;
			}
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

	function activateStep(stepId: string | undefined) {
		if (!stepId) return;
		if (onNodeActivate) {
			onNodeActivate(stepId);
		} else {
			selectedStepId = stepId;
		}
	}
</script>

<!-- The graph section's own controls now live in the page's full-width toolbar above it, matching the
	design, where they sit alongside the left tool rail rather than scoped to just this canvas column. -->
<section class="journey-graph" aria-label="Journey graph">
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
						viewBox="0 0 10 6"
						refX="5"
						refY="5"
						markerWidth="8"
						markerHeight="5"
						orient="auto"
					>
						<path d="M1 1 L5 5 L9 1" fill="none" stroke="#b1b4b6" stroke-width="1.5" />
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
							onselect={() => activateStep(node.data.stepId)}
							ariaLabel={node.ariaLabel}
						/>
					{:else if node.type === 'condition'}
						<ConditionNode ariaLabel={node.ariaLabel} />
					{:else}
						<TerminalNode data={node.data} />
					{/if}
				</div>
			{/each}

			{#each insertPoints as insertPoint (insertPoint.id)}
				<button
					type="button"
					class="journey-graph__insert"
					style:left="{insertPoint.x}px"
					style:top="{insertPoint.y}px"
					aria-label="Insert a step here"
					onclick={() => onInsertAfter?.(insertPoint.stepId, insertPoint.targetStepId)}
				>
					+
				</button>
			{/each}
		</div>

		<!-- The minimap and legend sit together as one footer row, so the legend always lands next to the
			minimap regardless of its own width rather than at a coordinate tuned for one particular size. -->
		<div class="journey-graph__canvas-footer">
			{#if contentWidth && contentHeight && canvasWidth && canvasHeight}
				<GraphMinimap
					{nodes}
					{contentWidth}
					{contentHeight}
					{panX}
					{panY}
					{zoom}
					{canvasWidth}
					{canvasHeight}
					onpan={(nextPanX, nextPanY) => {
						panX = nextPanX;
						panY = nextPanY;
					}}
				/>
			{/if}

			<!-- Explains the shapes once, here, rather than repeating a label on every node, so the canvas
				itself stays uncluttered. -->
			<ul class="journey-graph__legend">
				<li class="journey-graph__legend-item">
					<span class="journey-graph__legend-swatch journey-graph__legend-swatch--start"></span>
					Start
				</li>
				<li class="journey-graph__legend-item">
					<span class="journey-graph__legend-swatch journey-graph__legend-swatch--end"></span>
					End
				</li>
				<li class="journey-graph__legend-item">
					<span class="journey-graph__legend-swatch journey-graph__legend-swatch--condition"></span>
					Condition
				</li>
				<li class="journey-graph__legend-divider" aria-hidden="true"></li>
				<li class="journey-graph__legend-item">
					<span class="journey-graph__legend-swatch journey-graph__legend-swatch--selected"></span>
					Selected step
				</li>
			</ul>
		</div>
	</div>
</section>

<style>
	.journey-graph {
		display: flex;
		flex-direction: column;
		height: 100%;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.journey-graph__canvas {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
		overflow: hidden;
		background-color: #ffffff;
		background-image: radial-gradient(circle, #b1b4b6 1px, transparent 1px);
		background-size: 24px 24px;
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
		stroke: #b1b4b6;
		stroke-width: 1.5;
	}

	.journey-graph__node {
		position: absolute;
	}

	.journey-graph__insert {
		position: absolute;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		transform: translate(-50%, -50%);
		background-color: #1d70b8;
		border: 0;
		border-radius: 50%;
		color: #ffffff;
		font-size: 0.8125rem;
		font-weight: 700;
		line-height: 1;
		cursor: pointer;
	}

	.journey-graph__insert:hover,
	.journey-graph__insert:focus-visible {
		box-shadow: 0 0 0 3px #e1edf8;
		outline: none;
	}

	.journey-graph__canvas-footer {
		position: absolute;
		bottom: 15px;
		left: 15px;
		display: flex;
		align-items: flex-end;
		gap: 15px;
	}

	.journey-graph__legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 15px;
		margin: 0;
		padding: 8px 14px;
		list-style: none;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
		font-size: 0.6875rem;
		color: #505a5f;
	}

	.journey-graph__legend-item {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.journey-graph__legend-divider {
		width: 1px;
		height: 14px;
		background-color: #b1b4b6;
	}

	.journey-graph__legend-swatch {
		display: inline-block;
		width: 12px;
		height: 12px;
		flex-shrink: 0;
	}

	.journey-graph__legend-swatch--start {
		border-radius: 50%;
		background-color: #0b0c0c;
	}

	.journey-graph__legend-swatch--end {
		border-radius: 50%;
		background-color: #00703c;
		border: 2px solid #0b0c0c;
	}

	.journey-graph__legend-swatch--condition {
		width: 10px;
		height: 10px;
		background-color: #ffdd00;
		transform: rotate(45deg);
	}

	.journey-graph__legend-swatch--selected {
		box-sizing: border-box;
		border: 1.5px solid #1d70b8;
	}
</style>
