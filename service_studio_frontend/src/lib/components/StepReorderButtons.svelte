<script lang="ts">
	interface Props {
		label: string;
		canMoveUp: boolean;
		canMoveDown: boolean;
		onMoveUp: () => void;
		onMoveDown: () => void;
	}

	let { label, canMoveUp, canMoveDown, onMoveUp, onMoveDown }: Props = $props();
</script>

<!-- Arrow buttons used rather than drag handles for consistent interaction  -->
<div class="step-reorder" role="group" aria-label="Reorder {label}">
	<button
		type="button"
		class="step-reorder__button"
		disabled={!canMoveUp}
		aria-label="Move {label} up"
		onclick={onMoveUp}
	>
		<svg width="12" height="8" viewBox="0 0 12 8" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
			<path d="M1 6.5 L6 1.5 L11 6.5" fill="none" stroke="currentColor" stroke-width="2" />
		</svg>
	</button>
	<button
		type="button"
		class="step-reorder__button"
		disabled={!canMoveDown}
		aria-label="Move {label} down"
		onclick={onMoveDown}
	>
		<svg width="12" height="8" viewBox="0 0 12 8" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
			<path d="M1 1.5 L6 6.5 L11 1.5" fill="none" stroke="currentColor" stroke-width="2" />
		</svg>
	</button>
</div>

<style>
	.step-reorder {
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
		border: 1px solid #b1b4b6;
	}

	.step-reorder__button {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 26px;
		height: 21px;
		background: none;
		border: 0;
		padding: 0;
		color: #0b0c0c;
		cursor: pointer;
	}

	.step-reorder__button:first-child {
		border-bottom: 1px solid #b1b4b6;
	}

	.step-reorder__button:disabled {
		color: #b1b4b6;
		cursor: not-allowed;
	}
</style>
