<script lang="ts">
	import { SvelteFlowProvider } from '@xyflow/svelte';
	import JourneyGraphCanvas from './JourneyGraphCanvas.svelte';
	import type { JourneyStep } from '$lib/journey/types';

	interface Props {
		steps: JourneyStep[];
		selectedStepId?: string | null;
	}

	let { steps, selectedStepId = $bindable(null) }: Props = $props();
</script>

<!-- The provider owns shared viewport state so the header controls and canvas operate on the same graph instance. -->
<SvelteFlowProvider>
	<JourneyGraphCanvas {steps} bind:selectedStepId />
</SvelteFlowProvider>
