<script lang="ts">
	/*
		The Save draft button used in the editor and on every review page, with a line after it saying when the draft
		was saved, or that the browser would not store it. Each page says what saving means for it.
	*/

	interface Props {
		// Saves the draft, and gives false when the page did not save it, such as when its fields have problems, which
		// the page shows itself. The promise is rejected when the browser will not store the draft.
		onSave: () => Promise<boolean>;
	}

	let { onSave }: Props = $props();

	// The time the draft was last saved from this page, and whether the last save was refused by the browser.
	let savedAt = $state<Date>();
	let saveFailed = $state(false);

	async function save() {
		try {
			const saved = await onSave();
			saveFailed = false;
			// A save the page did not make takes away the time of an earlier one, so it is not read as just saved.
			savedAt = saved ? new Date() : undefined;
		} catch {
			saveFailed = true;
		}
	}
</script>

<button class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" type="button" onclick={save}>Save draft</button>
{#if saveFailed}
	<p class="govuk-error-message govuk-!-font-size-16 govuk-!-margin-bottom-0 save-draft__message" role="alert">The draft could not be saved in this browser</p>
{:else if savedAt}
	<p class="govuk-body-s govuk-!-margin-bottom-0 save-draft__message" role="status">
		Draft saved at {savedAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
	</p>
{/if}

<style>
	/* In a GOV.UK button group each button and link keeps 15px to its right, and the group has no gap of its own, so
		the line after the button keeps the same space before whatever comes next. */
	:global(.govuk-button-group) > .save-draft__message {
		margin-right: 15px;
	}
</style>
