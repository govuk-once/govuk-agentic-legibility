<script lang="ts">
	import { resolve } from '$app/paths';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	let selectedFileName = $state('');

	/**
	 * Shows the chosen document name so the visually hidden native input still gives clear confirmation.
	 */
	function handleFileSelection(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		selectedFileName = input.files?.[0]?.name ?? '';
	}
</script>

<svelte:head>
	<title>Describe the service | Service Studio</title>
</svelte:head>

<ServiceHeader />

<main class="onboard-details govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-details__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve('/onboard/method')}>Back</a>

		<h1 class="govuk-heading-xl">
			<span class="govuk-caption-l govuk-!-margin-bottom-5">Start a new service · step 2 of 2</span>
			Tell the assistant about the service
		</h1>
		<p class="govuk-body-l govuk-!-margin-bottom-6">
			It will use this, plus what is already on GOV.UK, to draft the journey and graph.
		</p>

		<!-- The GET form provides a working design journey without sending information to an external service. -->
		<form method="GET" action={resolve('/onboard/draft')}>
			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="service-name">What is the service called?</label>
				<input
					class="govuk-input"
					id="service-name"
					name="service-name"
					type="text"
					value="Change driving licence address"
				/>
			</div>

			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="service-description">What does the service do?</label>
				<textarea
					class="govuk-textarea govuk-!-margin-bottom-0"
					id="service-description"
					name="service-description"
					rows="4"
				>Change a user's driving licence address using either a postcode search or by entering the address manually.</textarea>
			</div>

			<fieldset class="govuk-fieldset govuk-form-group">
				<legend class="govuk-fieldset__legend govuk-!-font-weight-bold">Links to the service</legend>
				<label class="govuk-visually-hidden" for="service-link-1">First link to the service</label>
				<input
					class="govuk-input govuk-!-margin-bottom-2"
					id="service-link-1"
					name="service-links"
					type="url"
					value="https://www.gov.uk/change-address-driving-licence"
				/>
				<label class="govuk-visually-hidden" for="service-link-2">Second link to the service</label>
				<input
					class="govuk-input govuk-!-margin-bottom-2"
					id="service-link-2"
					name="service-links"
					type="url"
					placeholder="https://"
				/>
				<a class="govuk-link" href="#service-link-2">Add another link</a>
			</fieldset>

			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="service-document">Add a document (optional)</label>
				<!-- The native input covers the drop area so click, keyboard and file drop behaviour remain available. -->
				<div class="document-upload">
					<input
						class="document-upload__input"
						id="service-document"
						name="service-document"
						type="file"
						accept=".doc,.docx,.pdf,.txt"
						aria-describedby="service-document-hint"
						onchange={handleFileSelection}
					/>
					<span id="service-document-hint" class="document-upload__prompt govuk-body govuk-!-margin-bottom-0">
						<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
							<path d="M12 16 V4 M7 9 L12 4 L17 9 M5 15 V20 H19 V15" fill="none" stroke="currentColor" stroke-width="2" />
						</svg>
						<span class="document-upload__status">
							<span>Drop a policy paper, specification or form here, or choose a file.</span>
							{#if selectedFileName}
								<strong>Selected file: {selectedFileName}</strong>
							{/if}
						</span>
					</span>
				</div>
			</div>

			<div class="govuk-button-group">
				<button class="govuk-button" type="submit">
					<svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
						<path d="M9 0 L11 7 L18 9 L11 11 L9 18 L7 11 L0 9 L7 7 Z" fill="currentColor" />
					</svg>
					Generate the first draft
				</button>
				<span class="govuk-body">Usually under a minute</span>
			</div>
		</form>
	</div>
</main>

<style>
	/* The left edge matches the Service Studio name so each onboarding form uses the same visual column. */
	.onboard-details {
		margin-left: 145px;
	}

	.onboard-details__content {
		max-width: 700px;
	}

	.document-upload {
		position: relative;
		min-height: 80px;
		border: 2px dashed #505a5f;
	}

	.document-upload:focus-within {
		outline: 3px solid #ffdd00;
		outline-offset: 0;
	}

	.document-upload__input {
		position: absolute;
		inset: 0;
		z-index: 1;
		width: 100%;
		height: 100%;
		opacity: 0;
		cursor: pointer;
	}

	.document-upload__prompt {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 15px;
		min-height: 80px;
		padding: 15px;
	}

	.document-upload__status {
		display: flex;
		flex-direction: column;
		gap: 5px;
	}

	@media (max-width: 40.0525em) {
		.onboard-details {
			padding-right: 15px;
			padding-left: 15px;
			margin-left: 0;
		}

		.document-upload__prompt {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
