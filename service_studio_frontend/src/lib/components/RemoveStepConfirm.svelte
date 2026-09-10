<script lang="ts">
	interface Props {
		onRemove: () => void;
		onCancel: () => void;
	}

	let { onRemove, onCancel }: Props = $props();
</script>

<!-- An inline confirmation, rather than a browser dialog, keeps the interaction in the same GOV.UK styled
	surface. Shared between the collapsed and editing step cards so this confirmation is only built once. -->
<span class="remove-step-confirm">
	Remove this step?
	<button type="button" class="govuk-link remove-step-confirm__remove" onclick={onRemove}>Remove step</button>
	<button type="button" class="govuk-link" onclick={onCancel}>Keep step</button>
</span>

<style>
	.remove-step-confirm {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 1rem;
		color: #0b0c0c;
	}

	.remove-step-confirm :global(button.govuk-link) {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		cursor: pointer;
	}

	.remove-step-confirm__remove {
		color: #d4351c;
	}

	@media (max-width: 640px) {
		.remove-step-confirm {
			flex-wrap: wrap;
		}
	}
</style>
