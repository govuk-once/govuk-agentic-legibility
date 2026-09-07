<script lang="ts">
	import { SvelteFlowProvider } from '@xyflow/svelte';
	import JourneyGraphCanvas from './JourneyGraphCanvas.svelte';

	interface Props {
		onStepSelect: (stepId: string | null) => void;
	}

	let { onStepSelect }: Props = $props();
</script>

<!-- The provider owns shared viewport state so the header controls and canvas operate on the same graph instance. -->
<SvelteFlowProvider>
	<JourneyGraphCanvas {onStepSelect} />
</SvelteFlowProvider>
