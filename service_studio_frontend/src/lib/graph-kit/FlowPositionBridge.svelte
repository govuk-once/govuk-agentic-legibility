<script lang="ts">
	import { useSvelteFlow, type XYPosition } from '@xyflow/svelte';

	export type FlowInstance = {
		screenToFlowPosition: (position: XYPosition) => XYPosition;
	};

	interface Props {
		onready: (instance: FlowInstance) => void;
	}

	let { onready }: Props = $props();

	// useSvelteFlow only works from a component rendered inside the canvas itself, which the graph that owns
	// the canvas is not. This component exists to reach that context and hand screenToFlowPosition back up
	// through onready, so a drop at a point on the screen can be turned into a place on the canvas. It
	// renders nothing of its own.
	const flow = useSvelteFlow();

	$effect(() => {
		onready({ screenToFlowPosition: flow.screenToFlowPosition });
	});
</script>
