<script lang="ts">
  import ConditionNode from './ConditionNode.svelte';
  import RunStepNode from './RunStepNode.svelte';
  import TerminalNode from './TerminalNode.svelte';
  import GraphMinimap from './GraphMinimap.svelte';
  import { runToGraph } from './run-to-graph';
  import { layoutJourneyGraph, nodeSize } from './layout';
  import type { JourneyEdge, JourneyNode } from './types';
  import type { WorkflowDefinition } from './fsm';

  interface Props {
    definition: WorkflowDefinition;
    processId: string;
    currentStateId?: string | null;
  }

  let { definition, processId, currentStateId = null }: Props = $props();

  // Read-only: the graph is derived straight from the definition and current state in one chain, no sync
  // effect keeping a separate copy of nodes and edges in step with it. runToGraph and layoutJourneyGraph
  // are both pure, so this is safe.
  const built = $derived(runToGraph(definition, processId, currentStateId));
  const laid = $derived(layoutJourneyGraph(built.nodes, built.edges));
  const nodes = $derived(laid.nodes);
  const edges = $derived(built.edges);
  const contentWidth = $derived(laid.width);
  const contentHeight = $derived(laid.height);
  const nodeById = $derived(new Map(nodes.map((node) => [node.id, node])));
  // Used to detect when the node set itself changes (a different run or process), so the view refits only
  // then, not on every currentStateId highlight change within the same graph.
  const nodeSetKey = $derived(nodes.map((node) => node.id).join('|'));

  // Pan and zoom live outside the derived chain and drive only the viewport's CSS transform, so dragging
  // or zooming the canvas never re-runs the graph builder or layout.
  let panX = $state(0);
  let panY = $state(0);
  let isPanning = $state(false);
  let canvasEl = $state<HTMLDivElement | undefined>(undefined);
  // Tracked with a ResizeObserver, not bind:clientWidth, so a fit can read the canvas's real size even
  // before Svelte's own reactive size bindings re-run.
  let canvasWidth = $state(0);
  let canvasHeight = $state(0);

  // The interactive zoom range is wider than the fit range: fitting stops at 0.9 so a freshly opened
  // graph opens zoomed out a little, while a user can still zoom in further, to 1.5.
  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 1.5;
  const FIT_MAX_ZOOM = 0.9;
  const FIT_PADDING = 24;
  const ZOOM_STEP = 0.1;

  let zoom = $state(1);
  // Captures the pointer position and pan offset at the moment a drag starts, so the move handler can
  // compute the new pan purely from the distance dragged rather than accumulating per-frame deltas.
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
  // the set of nodes changes, so switching to a run on a different process reframes it. It does not fire
  // on pan, zoom, or a currentStateId change that leaves the node set the same, because it keys on
  // nodeSetKey, and applyFit writes only pan and zoom, which it does not read. The fit is run in a later
  // macrotask so the canvas is laid out at its CSS size first, and the key is latched only once a fit
  // actually lands, so a fit that measured too early is retried on the next change.
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
   * when a resize has not yet propagated to reactive state. The new zoom is worked out from the fit scale
   * alone, never from the current zoom, so repeated calls are stable.
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

  // Exposed so a page hosting this component can trigger a fit and step the zoom from its own toolbar,
  // via bind:this, rather than duplicating this math.
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
   * markup event handlers so the wheel listener can be registered non-passive, which is what lets it call
   * preventDefault to stop the page scrolling during a zoom.
   */
  function panZoom(node: HTMLDivElement) {
    // Start a pan, unless the pointer went down on a node, in which case the event is left alone (there
    // is nothing to click here, but a stray pan-start on a node would still fight its own hover/focus
    // styling).
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Element && event.target.closest('.journey-graph__node')) {
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

      // Normalise the delta so a mouse reporting lines or pages zooms at a similar rate to one reporting
      // pixels.
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

<!-- Read-only live-run visualization: no toolbar, no insert points, no selection — the only interaction
  is panning/zooming the canvas and reading the minimap, everything else is driven by the run's own
  progress. -->
<section class="journey-graph" aria-label="Run graph">
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
            <RunStepNode data={node.data} ariaLabel={node.ariaLabel} />
          {:else if node.type === 'condition'}
            <ConditionNode ariaLabel={node.ariaLabel} />
          {:else}
            <TerminalNode data={node.data} />
          {/if}
        </div>
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
          <span class="journey-graph__legend-swatch journey-graph__legend-swatch--current"></span>
          Current step
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

  .journey-graph__legend-swatch--current {
    box-sizing: border-box;
    border: 1.5px solid #1d70b8;
  }
</style>
