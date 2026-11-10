<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Pathname } from '$app/types';
	import ServiceHeader from '$lib/components/ServiceHeader.svelte';

	/*
		The page where a person describes what the assistant should draft: a name, a description and some links.
		The route gives the words and the addresses, so the same page serves a service and a form. The fields are
		posted under the names name, description and links, which the route's form action reads.
	*/

	interface Props {
		// What the draft is of, in one word, such as "service". It is used in the labels of the fields.
		subject: string;
		// The route of the page before this one, and the route the form posts to. That page asks the model for
		// the draft and shows the result. They are routes of the app, and this page resolves them. A kind of draft
		// that cannot be generated yet leaves the route out, and the button is then switched off.
		backRoute: Pathname;
		actionRoute?: Pathname;
		caption: string;
		heading: string;
		intro: string;
		// What the fields start with, so the page can be tried without typing.
		initial: { name: string; description: string; link: string };
	}

	let { subject, backRoute, actionRoute, caption, heading, intro, initial }: Props = $props();
</script>

<ServiceHeader />

<main class="onboard-details govuk-!-padding-top-9 govuk-!-padding-bottom-9">
	<div class="onboard-details__content">
		<a class="govuk-back-link govuk-!-margin-bottom-5" href={resolve(backRoute)}>Back</a>

		<h1 class="govuk-heading-xl">
			<span class="govuk-caption-l govuk-!-margin-bottom-5">{caption}</span>
			{heading}
		</h1>
		<p class="govuk-body-l govuk-!-margin-bottom-6">{intro}</p>

		<!-- Posts to the draft page's own form action, which asks the model for the draft and shows the result there.
			A plain full page POST needs no client side script. -->
		<form method="POST" action={actionRoute ? resolve(actionRoute) : undefined}>
			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="onboard-name">What is the {subject} called?</label>
				<input class="govuk-input" id="onboard-name" name="name" type="text" value={initial.name} />
			</div>

			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="onboard-description">What does the {subject} do?</label>
				<textarea
					class="govuk-textarea govuk-!-margin-bottom-0"
					id="onboard-description"
					name="description"
					rows="4"
					value={initial.description}
				></textarea>
			</div>

			<fieldset class="govuk-fieldset govuk-form-group">
				<legend class="govuk-fieldset__legend govuk-!-font-weight-bold">Links to the {subject}</legend>
				<label class="govuk-visually-hidden" for="onboard-link-1">First link to the {subject}</label>
				<input
					class="govuk-input govuk-!-margin-bottom-2"
					id="onboard-link-1"
					name="links"
					type="url"
					value={initial.link}
				/>
				<label class="govuk-visually-hidden" for="onboard-link-2">Second link to the {subject}</label>
				<input
					class="govuk-input govuk-!-margin-bottom-2"
					id="onboard-link-2"
					name="links"
					type="url"
					placeholder="https://"
				/>
				<a class="govuk-link" href="#onboard-link-2">Add another link</a>
			</fieldset>

			<div class="govuk-form-group">
				<label class="govuk-label govuk-label--s" for="onboard-document">Add a document (optional)</label>
				<!-- Not wired into generation yet, disabled so it does not suggest it does something it does not. -->
				<div class="document-upload document-upload--disabled">
					<input
						class="document-upload__input"
						id="onboard-document"
						name="document"
						type="file"
						accept=".doc,.docx,.pdf,.txt"
						aria-describedby="onboard-document-hint"
						disabled
					/>
					<span id="onboard-document-hint" class="document-upload__prompt govuk-body govuk-!-margin-bottom-0">
						<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
							<path d="M12 16 V4 M7 9 L12 4 L17 9 M5 15 V20 H19 V15" fill="none" stroke="currentColor" stroke-width="2" />
						</svg>
						<span class="document-upload__status">
							<span>Not available yet. The draft is generated from the description and links above.</span>
						</span>
					</span>
				</div>
			</div>

			<div class="govuk-button-group">
				<button class="govuk-button" type="submit" disabled={!actionRoute}>
					<svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
						<path d="M9 0 L11 7 L18 9 L11 11 L9 18 L7 11 L0 9 L7 7 Z" fill="currentColor" />
					</svg>
					Generate the first draft
				</button>
				<span class="govuk-body">{actionRoute ? 'Usually under a minute' : 'Not available yet'}</span>
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

	.document-upload--disabled {
		border-color: #b1b4b6;
	}

	.document-upload--disabled .document-upload__prompt {
		color: #b1b4b6;
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

	.document-upload__input:disabled {
		cursor: not-allowed;
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
