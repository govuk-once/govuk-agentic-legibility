<script lang="ts">
	import { NOTE_MAX_LENGTH, displayUrl, parseContextUrl } from './context';
	import type { ContextItem } from './context';

	interface Props {
		items: ContextItem[];
		// Called with the whole new list every time an item is added, changed or removed, so the page that
		// owns the items stays the one place they are held.
		onChange: (items: ContextItem[]) => void;
	}

	let { items, onChange }: Props = $props();

	// The component identifier keeps label targets unique when more than one editor is on the page.
	const componentId = $props.id();

	// Which form is showing, if any. Only one at a time, so opening one closes the other. editingId is set
	// when an existing note is being changed rather than a new one added.
	let form = $state<{ kind: 'url' } | { kind: 'note'; editingId: string | null } | null>(null);

	// Held locally so typing does not touch the saved items until Add URL or Save note is pressed.
	let draftUrl = $state('');
	let draftPurpose = $state('');
	let draftNote = $state('');
	let urlError = $state<string | null>(null);
	let noteError = $state<string | null>(null);

	const noteLength = $derived(draftNote.length);
	const noteTooLong = $derived(noteLength > NOTE_MAX_LENGTH);

	/**
	 * Closes whichever form is open and clears what was typed into it, so the next one starts empty.
	 */
	function closeForm() {
		form = null;
		draftUrl = '';
		draftPurpose = '';
		draftNote = '';
		urlError = null;
		noteError = null;
	}

	/**
	 * Opens the empty form for adding a web page.
	 */
	function openUrlForm() {
		closeForm();
		form = { kind: 'url' };
	}

	/**
	 * Opens the note form, empty for a new note or filled with the existing text when changing one.
	 */
	function openNoteForm(existing?: ContextItem) {
		closeForm();
		form = { kind: 'note', editingId: existing?.id ?? null };
		if (existing?.kind === 'note') draftNote = existing.text;
	}

	/**
	 * Checks the web address, then adds it to the list and closes the form. An address that does not pass
	 * stays in the field with an error beside it.
	 */
	function submitUrl() {
		const result = parseContextUrl(draftUrl);
		if (!result.ok) {
			urlError = result.error;
			return;
		}
		onChange([
			...items,
			{ id: crypto.randomUUID(), kind: 'url', url: result.url, purpose: draftPurpose.trim() }
		]);
		closeForm();
	}

	/**
	 * Checks the note, then either adds it or replaces the one being changed, and closes the form.
	 */
	function submitNote() {
		const text = draftNote.trim();
		if (!text) {
			noteError = 'Enter a note';
			return;
		}
		if (text.length > NOTE_MAX_LENGTH) {
			noteError = `Note must be ${NOTE_MAX_LENGTH} characters or fewer`;
			return;
		}

		const editingId = form?.kind === 'note' ? form.editingId : null;
		if (editingId) {
			onChange(items.map((item) => (item.id === editingId ? { ...item, text } : item)));
		} else {
			onChange([...items, { id: crypto.randomUUID(), kind: 'note', text }]);
		}
		closeForm();
	}

	/**
	 * Removes one item from the list. If the note being removed is the one open in the form, the form
	 * closes too, so nothing is left editing something that no longer exists.
	 */
	function removeItem(id: string) {
		onChange(items.filter((item) => item.id !== id));
		if (form?.kind === 'note' && form.editingId === id) closeForm();
	}
</script>

<!-- The native details element gives the open and close, with keyboard and screen reader support, for
	free. It is the GOV.UK Details component, so the triangle and the underlined link come from its own
	styles rather than anything drawn here. -->
<details class="govuk-details step-context">
	<summary class="govuk-details__summary">
		<span class="govuk-details__summary-text">Add context for the agent</span>
	</summary>

	<div class="govuk-details__text step-context__body">
		<p class="govuk-hint govuk-!-margin-bottom-0">
			{items.length === 0
				? 'Add a web page or write a short note. The agent can read it when it handles this step.'
				: 'Guidance the agent can read when it handles this step.'}
		</p>

		{#if items.length > 0}
			<ul class="step-context__list">
				{#each items as item (item.id)}
					<li class="step-context__item">
						{#if item.kind === 'url'}
							<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">
								{item.purpose || displayUrl(item.url)}
							</p>
							<p class="govuk-body-s govuk-!-margin-bottom-0 step-context__link">
								<a class="govuk-link" href={item.url} target="_blank" rel="noopener noreferrer">
									{displayUrl(item.url)}<span class="govuk-visually-hidden"> (opens in a new tab)</span>
								</a>
							</p>
							<div class="step-context__item-actions">
								<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0 step-context__remove" onclick={() => removeItem(item.id)}>
									Remove<span class="govuk-visually-hidden"> web page {displayUrl(item.url)}</span>
								</button>
							</div>
						{:else}
							<p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-bottom-0">Note</p>
							<p class="govuk-body-s govuk-!-margin-bottom-0 step-context__note-text">{item.text}</p>
							<div class="step-context__item-actions">
								<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={() => openNoteForm(item)}>
									Change<span class="govuk-visually-hidden"> note</span>
								</button>
								<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0 step-context__remove" onclick={() => removeItem(item.id)}>
									Remove<span class="govuk-visually-hidden"> note</span>
								</button>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}

		{#if form?.kind === 'url'}
			<form
				class="step-context__form"
				novalidate
				onsubmit={(event) => {
					event.preventDefault();
					submitUrl();
				}}
			>
				<h3 class="govuk-heading-s govuk-!-margin-bottom-0">Add a web page</h3>

				<div class="govuk-form-group step-context__form-group" class:govuk-form-group--error={urlError}>
					<label class="govuk-label govuk-label--s" for="{componentId}-url">Web address</label>
					<div id="{componentId}-url-hint" class="govuk-hint govuk-!-margin-bottom-1">
						We read the page and keep a copy. The agent can quote from it when it handles this step.
					</div>
					{#if urlError}
						<p id="{componentId}-url-error" class="govuk-error-message">
							<span class="govuk-visually-hidden">Error:</span> {urlError}
						</p>
					{/if}
					<input
						class="govuk-input"
						class:govuk-input--error={urlError}
						id="{componentId}-url"
						name="context-url"
						type="url"
						inputmode="url"
						autocomplete="off"
						aria-describedby="{componentId}-url-hint{urlError ? ` ${componentId}-url-error` : ''}"
						bind:value={draftUrl}
					/>
				</div>

				<div class="govuk-form-group step-context__form-group">
					<label class="govuk-label govuk-label--s" for="{componentId}-purpose">
						What is it for? (optional)
					</label>
					<input
						class="govuk-input"
						id="{componentId}-purpose"
						name="context-purpose"
						type="text"
						placeholder="e.g. Eligibility rules"
						bind:value={draftPurpose}
					/>
				</div>

				<div class="step-context__form-actions">
					<button class="govuk-button govuk-!-margin-bottom-0" type="submit">Add URL</button>
					<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={closeForm}>
						Cancel
					</button>
				</div>
			</form>
		{:else if form?.kind === 'note'}
			<form
				class="step-context__form"
				novalidate
				onsubmit={(event) => {
					event.preventDefault();
					submitNote();
				}}
			>
				<h3 class="govuk-heading-s govuk-!-margin-bottom-0">{form.editingId ? 'Edit note' : 'Add a note'}</h3>

				<div class="govuk-form-group step-context__form-group" class:govuk-form-group--error={noteError || noteTooLong}>
					<label class="govuk-label govuk-label--s" for="{componentId}-note">Note</label>
					{#if noteError}
						<p id="{componentId}-note-error" class="govuk-error-message">
							<span class="govuk-visually-hidden">Error:</span> {noteError}
						</p>
					{/if}
					<textarea
						class="govuk-textarea govuk-!-margin-bottom-1"
						class:govuk-textarea--error={noteError || noteTooLong}
						id="{componentId}-note"
						name="context-note"
						rows="5"
						aria-describedby="{componentId}-note-help{noteError ? ` ${componentId}-note-error` : ''}"
						bind:value={draftNote}
					></textarea>
					<div id="{componentId}-note-help" class="step-context__note-help">
						<span class="govuk-hint govuk-!-margin-bottom-0">Only the agent sees this.</span>
						<span
							class="govuk-character-count__message"
							class:govuk-error-message={noteTooLong}
							class:govuk-hint={!noteTooLong}
							aria-live="polite"
						>
							{noteLength} of {NOTE_MAX_LENGTH} characters
						</span>
					</div>
				</div>

				<div class="step-context__form-actions">
					<button class="govuk-button govuk-!-margin-bottom-0" type="submit">Save note</button>
					<button type="button" class="govuk-link govuk-body-s govuk-!-margin-bottom-0" onclick={closeForm}>
						Cancel
					</button>
					{#if form.editingId}
						<button
							type="button"
							class="govuk-link govuk-body-s govuk-!-margin-bottom-0 step-context__remove step-context__form-delete"
							onclick={() => form?.kind === 'note' && form.editingId && removeItem(form.editingId)}
						>
							Delete
						</button>
					{/if}
				</div>
			</form>
		{:else}
			<!-- Secondary buttons, the closest GOV.UK has to the design's outlined add buttons. -->
			<div class="step-context__add-buttons">
				<button class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" type="button" onclick={openUrlForm}>
					Add URL
				</button>
				<button class="govuk-button govuk-button--secondary govuk-!-margin-bottom-0" type="button" onclick={() => openNoteForm()}>
					Add note
				</button>
			</div>
		{/if}
	</div>
</details>

<style>
	.step-context {
		margin-bottom: 0;
	}

	/* GOV.UK's own details text carries a grey left border and matching left padding, dropped here so the
		open section lines up with the fields above and below it. */
	.step-context__body {
		padding-left: 0;
		border-left: 0;
		display: flex;
		flex-direction: column;
		gap: 15px;
	}

	.step-context__list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.step-context__item {
		display: flex;
		flex-direction: column;
		gap: 5px;
		padding: 10px 15px;
		background-color: #ffffff;
		border: 1px solid #b1b4b6;
	}

	.step-context__link,
	.step-context__note-text {
		/* A long address or an unbroken word must wrap inside the narrow panel rather than push it wider. */
		overflow-wrap: anywhere;
	}

	.step-context__note-text {
		white-space: pre-wrap;
	}

	.step-context__item-actions,
	.step-context__form-actions {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.step-context__remove {
		color: #d4351c;
	}

	.step-context__form {
		display: flex;
		flex-direction: column;
		gap: 15px;
		padding: 15px;
		background-color: #f3f7fb;
		border: 2px solid #1d70b8;
	}

	.step-context__form-group {
		margin-bottom: 0;
	}

	.step-context__form-delete {
		margin-left: auto;
	}

	.step-context__note-help {
		display: flex;
		justify-content: space-between;
		gap: 15px;
	}

	.step-context__add-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}
</style>
