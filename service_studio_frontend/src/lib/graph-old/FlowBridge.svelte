<script lang="ts">
	import { useSvelteFlow, type XYPosition } from '@xyflow/svelte';

	export type FlowInstance = {
		screenToFlowPosition: (position: XYPosition) => XYPosition;
	};

	interface Props {
		onready: (instance: FlowInstance) => void;
	}

	let { onready }: Props = $props();

	// useSvelteFlow only works from a component rendered inside SvelteFlow itself, which JourneyGraph.svelte
	// is not, so this component exists purely to reach that context and hand screenToFlowPosition back up
	// to the parent through onready, for turning a native drag-and-drop's screen coordinates into a flow
	// position. It renders nothing of its own.
	const flow = useSvelteFlow();

	$effect(() => {
		onready({ screenToFlowPosition: flow.screenToFlowPosition });
	});
</script>
