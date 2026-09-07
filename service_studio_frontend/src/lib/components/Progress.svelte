<script lang="ts">
	type StageState = 'complete' | 'current' | 'upcoming';

	interface Stage {
		number: number;
		label: string;
		state: StageState;
	}

	let { stages }: { stages: Stage[] } = $props();
</script>

<!-- The progress navigation communicates completed, current and upcoming prototype stages in one sequence. -->
<nav class="progress" aria-label="Prototype stages">
	{#each stages as stage, index (stage.number)}
		{#if index > 0}
			<!-- Dividers separate neighbouring stages without adding another item to the sequence. -->
			<span class="progress__divider"></span>
		{/if}
		<div class="progress__stage">
			{#if stage.state === 'complete'}
				<span class="progress__marker progress__marker--complete">
					<svg width="14" height="11" viewBox="0 0 14 11" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
						<path d="M1 5.5 L5 9.5 L13 1.5" fill="none" stroke="#ffffff" stroke-width="2.5" />
					</svg>
				</span>
			{:else}
				<span
					class="progress__marker"
					class:progress__marker--current={stage.state === 'current'}
				>
					{stage.number}
				</span>
			{/if}
			<span
				class="progress__label"
				class:progress__label--current={stage.state === 'current'}
			>
				{stage.label}
			</span>
		</div>
	{/each}
</nav>

<style>
	.progress {
		display: flex;
		align-items: center;
		padding: 25px 40px 0;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.progress__stage {
		display: flex;
		align-items: center;
		gap: 10px;
		padding-inline: 20px;
	}

	.progress__stage:first-child {
		padding-left: 0;
	}

	.progress__divider {
		width: 1px;
		height: 28px;
		background-color: #b1b4b6;
	}

	.progress__marker {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 28px;
		height: 28px;
		border: 2px solid #b1b4b6;
		font-size: 1rem;
		font-weight: 700;
		color: #505a5f;
	}

	.progress__marker--complete {
		background-color: #00703c;
		border: 0;
	}

	.progress__marker--current {
		background-color: #1d70b8;
		border: 0;
		color: #ffffff;
	}

	.progress__label {
		font-size: 1rem;
		line-height: 1.25;
		color: #505a5f;
	}

	.progress__label--current {
		font-weight: 700;
		color: #0b0c0c;
	}
</style>
