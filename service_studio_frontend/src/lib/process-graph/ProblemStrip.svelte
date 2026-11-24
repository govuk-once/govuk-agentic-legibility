<script lang="ts">
	import { useNodes, useStore, useSvelteFlow, useViewport, type Node } from '@xyflow/svelte';
	import type { ProblemMark } from './process-graph-types';

	/*
		A thin strip down the right edge of the canvas that shows where the problems are in a long journey, and moves
		the canvas up and down the journey. The top of the strip is the top of the graph and the bottom is the bottom of
		the graph, so each mark is as far down the strip as its step is down the journey, red for an error and yellow
		for a warning.

		1. The blue handle is a slider for how far down the journey the canvas is. It is always the same size, like the
		   handle of a physical slider, and is as far down the strip as the middle of what is on screen is down the
		   journey. Dragging it, or pressing
		   anywhere on the strip, moves the canvas, and so do the arrow keys, Page Up, Page Down, Home and End when it
		   has focus.
		2. Each mark is a button that moves the canvas to its step. The marks are drawn over the slider and are not
		   inside it, because a slider holds no buttons of its own.

		It is only drawn while there is a problem to mark, so it reads as a way to find problems and never as a scroll
		bar for the list of steps beside it. It has to be drawn inside the canvas, because the view and the places of
		the shapes can only be read there.
	*/

	interface Props {
		marks: ProblemMark[];
	}

	let { marks }: Props = $props();

	const flow = useSvelteFlow();
	const nodes = useNodes();
	const viewport = useViewport();
	const store = useStore();

	// The height of the handle in pixels. The marks are placed on the same scale as the handle.
	const handleHeight = 40;

	// Whether the handle is being dragged, so moving the pointer moves the canvas until it is let go.
	let dragging = $state(false);

	// The shapes of the process, leaving out the module borders, which have no state of their own and only follow the
	// shapes inside them.
	const stateNodes = $derived(nodes.current.filter((node) => typeof node.data.stateId === 'string'));

	// The area the whole graph covers on the canvas.
	const bounds = $derived(flow.getNodesBounds(stateNodes));

	// Gives how far down the graph a place on the canvas is, from 0 at the top to 1 at the bottom.
	function shareOfHeight(y: number): number {
		return bounds.height > 0 ? Math.min(1, Math.max(0, (y - bounds.y) / bounds.height)) : 0;
	}

	// Gives the CSS top of the middle of a handle or mark that sits a share of the way down the strip.
	function topOf(share: number): string {
		return `calc(${share} * (100% - ${handleHeight}px) + ${handleHeight / 2}px)`;
	}

	// The middle of a shape on the canvas. Svelte Flow measures each shape once it is drawn, and the size set on it by
	// the layout is used until then.
	function middleOf(node: Node): { x: number; y: number } {
		const width = node.measured?.width ?? node.width ?? 0;
		const height = node.measured?.height ?? node.height ?? 0;
		return { x: node.position.x + width / 2, y: node.position.y + height / 2 };
	}

	// Each mark with the middle of its step, and how far down the strip it sits. A problem with a state that is not
	// drawn, such as one hidden with the developer states, has no mark.
	const placedMarks = $derived(
		marks.flatMap((mark) => {
			const node = stateNodes.find((each) => each.data.stateId === mark.stateId);
			if (!node) return [];
			const middle = middleOf(node);
			return [{ ...mark, middle, share: shareOfHeight(middle.y) }];
		})
	);

	// The middle of what is on screen, on the canvas, and how far down the graph it is.
	const screenMiddle = $derived.by(() => {
		const { x, y, zoom } = viewport.current;
		const middle = { x: (store.width / 2 - x) / zoom, y: (store.height / 2 - y) / zoom };
		return { ...middle, share: shareOfHeight(middle.y) };
	});

	// Moves the canvas so a place on the graph is in the middle of the screen, keeping the zoom as it is. A move made
	// while dragging is not animated, so the canvas keeps up with the pointer.
	function moveTo(x: number, y: number, duration = 300) {
		flow.setCenter(x, y, { zoom: viewport.current.zoom, duration });
	}

	// Moves the canvas so the middle of the screen is a share of the way down the journey.
	function moveToShare(share: number, duration?: number) {
		moveTo(screenMiddle.x, bounds.y + Math.min(1, Math.max(0, share)) * bounds.height, duration);
	}

	// Gives how far down the strip the pointer is, measured so the middle of the handle follows the pointer.
	function shareAtPointer(event: PointerEvent & { currentTarget: HTMLDivElement }): number {
		const box = event.currentTarget.getBoundingClientRect();
		return (event.clientY - box.top - handleHeight / 2) / (box.height - handleHeight);
	}

	// Pressing the strip moves the handle there and starts a drag. The pointer is captured, so the drag carries on when
	// the pointer leaves the strip.
	function startDrag(event: PointerEvent & { currentTarget: HTMLDivElement }) {
		event.currentTarget.setPointerCapture(event.pointerId);
		dragging = true;
		moveToShare(shareAtPointer(event), 0);
	}

	function drag(event: PointerEvent & { currentTarget: HTMLDivElement }) {
		if (dragging) moveToShare(shareAtPointer(event), 0);
	}

	// The steps the keys move the handle by, as a share of the journey.
	const keySteps: Record<string, (share: number) => number> = {
		ArrowUp: (share) => share - 0.05,
		ArrowDown: (share) => share + 0.05,
		PageUp: (share) => share - 0.25,
		PageDown: (share) => share + 0.25,
		Home: () => 0,
		End: () => 1
	};

	function moveWithKey(event: KeyboardEvent) {
		const step = keySteps[event.key];
		if (!step) return;
		event.preventDefault();
		moveToShare(step(screenMiddle.share));
	}
</script>

<div class="problem-strip">
	<div
		class="problem-strip__track"
		role="slider"
		tabindex="0"
		aria-label="Position in the journey"
		aria-orientation="vertical"
		aria-valuemin={0}
		aria-valuemax={100}
		aria-valuenow={Math.round(screenMiddle.share * 100)}
		aria-valuetext="{Math.round(screenMiddle.share * 100)}% of the way down the journey"
		onpointerdown={startDrag}
		onpointermove={drag}
		onpointerup={() => (dragging = false)}
		onpointercancel={() => (dragging = false)}
		onkeydown={moveWithKey}
	>
		<div class="problem-strip__handle" style:top={topOf(screenMiddle.share)} style:height="{handleHeight}px"></div>
	</div>

	{#each placedMarks as mark (`${mark.stateId}-${mark.severity}-${mark.label}`)}
		<button
			type="button"
			class="problem-strip__mark problem-strip__mark--{mark.severity}"
			style:top={topOf(mark.share)}
			aria-label={mark.label}
			title={mark.label}
			onclick={() => moveTo(mark.middle.x, mark.middle.y)}
		></button>
	{/each}
</div>

<style>
	/* Drawn over the right edge of the canvas, above the shapes and the lines. */
	.problem-strip {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 5;
		width: 15px;
		background-color: #f3f2f1;
		border-left: 1px solid #b1b4b6;
	}

	.problem-strip__track {
		position: absolute;
		inset: 0;
		cursor: pointer;
		touch-action: none;
	}

	.problem-strip__track:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 0;
	}

	.problem-strip__handle {
		position: absolute;
		left: 0;
		right: 0;
		box-sizing: border-box;
		background-color: #ffffff;
		border: 2px solid #1d70b8;
		transform: translateY(-50%);
		cursor: grab;
	}

	/* The button is taller than the mark it draws, so it is easier to choose. */
	.problem-strip__mark {
		position: absolute;
		left: 0;
		right: 0;
		height: 15px;
		padding: 0;
		background: none;
		border: 0;
		transform: translateY(-50%);
		cursor: pointer;
	}

	.problem-strip__mark::before {
		content: '';
		position: absolute;
		top: 5px;
		left: 2px;
		right: 2px;
		height: 5px;
	}

	.problem-strip__mark--error::before {
		background-color: #d4351c;
	}

	.problem-strip__mark--warning::before {
		background-color: #ffdd00;
	}

	.problem-strip__mark:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 0;
		box-shadow: inset 0 0 0 2px #0b0c0c;
	}
</style>
