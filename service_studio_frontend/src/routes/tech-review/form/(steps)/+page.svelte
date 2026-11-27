<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ReviewStep from '$lib/components/ReviewStep.svelte';
	import ErrorSummary from '$lib/form-editor/components/ErrorSummary.svelte';
	import { techReviewSteps } from '$lib/form-editor/review-steps';
	import SaveDraftButton from '$lib/form-editor/components/SaveDraftButton.svelte';
	import { saveReviewedForm } from '$lib/form-editor/review-draft';
	import { describeDuration } from '$lib/process-graph/describe-value';
	import { stateTitle } from '$lib/process-graph/process-to-graph';
	import { durationFrom, durationInSeconds, timeUnits, type TimeUnit } from '$lib/schema/workflow/durations';
	import {
		longestWait,
		withWorkflowSettings,
		workflowSettingsOf,
		workflowSettingsProblems,
		type WorkflowSettings,
		type WorkflowSettingsField,
		type WorkflowSettingsProblem
	} from '$lib/schema/workflow/workflow-settings';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// The settings the form already holds, which fill the fields when the page opens. What is typed is read from the
	// fields when the person continues, and only written to the form when it passes its check.
	const saved = $derived(workflowSettingsOf(data.workflow.manifest));

	// The run timeout as it is typed, so the line under it can say straight away whether it is long enough.
	let runTimeout = $derived(saved.runTimeout);
	let runTimeoutUnit = $derived(saved.runTimeoutUnit);

	// The longest wait in the journey, described by what it waits for, and whether the run timeout covers it.
	const process = $derived(data.workflow.processes[data.workflow.manifest.entry]);
	const wait = $derived.by(() => {
		const found = longestWait(process);
		if (!found) return undefined;
		const state = process.states[found.code];
		const duration = state.state_type === 'wait' && typeof state.duration === 'string' ? state.duration : '';
		const runSeconds = /^\d+$/.test(runTimeout.trim()) ? durationInSeconds(durationFrom(Number(runTimeout), runTimeoutUnit)) : 0;
		// A wait's title usually starts "Wait for", such as "Wait for the form to be processed". Those words are taken
		// off so the line reads "Long enough for the form to be processed" rather than naming the kind of step. A title
		// written another way is used as it is.
		const subject = stateTitle(state, found.code).replace(/^wait for\s+/i, '');
		return { subject, length: describeDuration(duration), enough: (runSeconds ?? 0) >= found.seconds };
	});

	// The problems found when the person last tried to continue, shown only after that.
	let problems = $state<WorkflowSettingsProblem[]>([]);
	const problemFor = (field: WorkflowSettingsField) => problems.find((problem) => problem.field === field)?.message;

	let settingsForm = $state<HTMLFormElement>();

	// The id of each field, so the error summary can link to it.
	const fieldIds: Record<WorkflowSettingsField, string> = {
		runTimeout: 'run-timeout',
		runTimeoutUnit: 'run-timeout-unit',
		callTimeout: 'call-timeout',
		attempts: 'call-attempts',
		pauseBetween: 'call-pause'
	};

	// Reads what is typed in each field.
	function readSettings(form: HTMLFormElement): WorkflowSettings {
		const fields = new FormData(form);
		const read = (field: WorkflowSettingsField) => String(fields.get(field) ?? '');
		return {
			runTimeout: read('runTimeout'),
			runTimeoutUnit: read('runTimeoutUnit') as TimeUnit,
			callTimeout: read('callTimeout'),
			attempts: read('attempts'),
			pauseBetween: read('pauseBetween')
		};
	}

	/**
	 * Checks what is typed and, when every field passes, saves it into the draft. When any field has a problem nothing
	 * is saved, and the problems are listed at the top. Says whether the settings were saved.
	 */
	async function saveSettings(form: HTMLFormElement): Promise<boolean> {
		const settings = readSettings(form);
		problems = workflowSettingsProblems(settings);
		if (problems.length > 0) return false;
		await saveReviewedForm(data.draft, { stage: 'Tech review', workflow: { ...data.workflow, manifest: withWorkflowSettings(data.workflow.manifest, settings) } });
		return true;
	}

	// Saves the settings and goes on to the Flex connections. The layout opened the form before the settings were
	// changed, so it is opened again to pick them up.
	async function continueToFlex(event: SubmitEvent & { currentTarget: HTMLFormElement }) {
		event.preventDefault();
		if (await saveSettings(event.currentTarget)) await goto(resolve('/tech-review/form/flex'), { invalidateAll: true });
	}

	// Saves the settings and stays on the page, so the developer can come back to the review later. The form is opened
	// again so the page holds what was just saved.
	async function saveSettingsDraft(): Promise<boolean> {
		if (!settingsForm || !(await saveSettings(settingsForm))) return false;
		await invalidateAll();
		return true;
	}
</script>

<svelte:head>
	<title>{problems.length > 0 ? 'Error: ' : ''}Workflow settings: Technical review | Service Studio</title>
</svelte:head>

{#snippet errorMessage(field: WorkflowSettingsField)}
	{@const problem = problemFor(field)}
	{#if problem}
		<p id="{fieldIds[field]}-error" class="govuk-error-message">
			<span class="govuk-visually-hidden">Error:</span>
			{problem}
		</p>
	{/if}
{/snippet}

<!-- A number of a fixed unit, with the unit written after the field. -->
{#snippet numberField(field: WorkflowSettingsField, label: string, unit: string)}
	{@const problem = problemFor(field)}
	<div class="govuk-form-group govuk-!-margin-bottom-0" class:govuk-form-group--error={problem}>
		<label class="govuk-label govuk-label--s" for={fieldIds[field]}>{label}</label>
		{@render errorMessage(field)}
		<div class="govuk-input__wrapper">
			<input
				class="govuk-input govuk-input--width-3"
				class:govuk-input--error={problem}
				id={fieldIds[field]}
				name={field}
				type="text"
				inputmode="numeric"
				spellcheck="false"
				aria-describedby={problem ? `${fieldIds[field]}-error` : undefined}
				value={saved[field]}
			/>
			<div class="govuk-input__suffix" aria-hidden="true">{unit}</div>
		</div>
	</div>
{/snippet}

<ReviewStep
	steps={techReviewSteps(['current', 'upcoming', 'upcoming', 'upcoming'])}
	heading="Workflow settings"
	hint="These apply to the whole journey. Individual steps can override the API call defaults later."
>
	<ErrorSummary problems={problems.map((problem) => ({ fieldId: fieldIds[problem.field], message: problem.message }))} />

	<form id="workflow-settings" novalidate onsubmit={continueToFlex} bind:this={settingsForm}>
		<div class="govuk-grid-row">
			<div class="govuk-grid-column-one-third">
				<h2 class="govuk-heading-s govuk-!-margin-bottom-1">Run timeout</h2>
				<p class="govuk-hint" id="run-timeout-hint">How long the whole run can last. 7 days for forms.</p>
			</div>
			<div class="govuk-grid-column-two-thirds">
				<div class="govuk-form-group govuk-!-margin-bottom-2" class:govuk-form-group--error={problemFor('runTimeout')}>
					{@render errorMessage('runTimeout')}
					<div class="workflow-settings__fields">
						<label class="govuk-visually-hidden" for={fieldIds.runTimeout}>Run timeout</label>
						<input
							class="govuk-input govuk-input--width-3"
							class:govuk-input--error={problemFor('runTimeout')}
							id={fieldIds.runTimeout}
							name="runTimeout"
							type="text"
							inputmode="numeric"
							spellcheck="false"
							aria-describedby="run-timeout-hint{problemFor('runTimeout') ? ' run-timeout-error' : ''}"
							value={saved.runTimeout}
							oninput={(event) => (runTimeout = event.currentTarget.value)}
						/>
						<label class="govuk-visually-hidden" for={fieldIds.runTimeoutUnit}>Unit of the run timeout</label>
						<select
							class="govuk-select workflow-settings__unit"
							id={fieldIds.runTimeoutUnit}
							name="runTimeoutUnit"
							value={saved.runTimeoutUnit}
							onchange={(event) => (runTimeoutUnit = event.currentTarget.value as TimeUnit)}
						>
							{#each timeUnits as { unit } (unit)}
								<option value={unit}>{unit}</option>
							{/each}
						</select>
					</div>
				</div>
				{#if wait}
					<p class="govuk-body-s govuk-!-margin-bottom-0 {wait.enough ? 'status-text-done' : 'status-text-problem'}">
						{wait.enough ? 'Long enough for' : 'Too short for'}
						{wait.subject}, which waits {wait.length}.
					</p>
				{/if}
			</div>
		</div>

		<hr class="govuk-section-break govuk-section-break--l govuk-section-break--visible" />

		<div class="govuk-grid-row">
			<div class="govuk-grid-column-one-third">
				<h2 class="govuk-heading-s govuk-!-margin-bottom-1">API call defaults</h2>
				<p class="govuk-hint">Used by every API call unless the step sets its own custom settings in a later stage.</p>
			</div>
			<div class="govuk-grid-column-two-thirds">
				<div class="workflow-settings__fields workflow-settings__fields--labelled">
					{@render numberField('callTimeout', 'Timeout', 'seconds')}
					{@render numberField('attempts', 'Attempts', 'times')}
					{@render numberField('pauseBetween', 'Pause between', 'seconds')}
				</div>
			</div>
		</div>
	</form>

	{#snippet actions()}
		<!-- Back leaves the technical review for the owner review that comes before it. Nothing typed here is saved
			unless Save draft is chosen first. -->
		<a class="govuk-link" href={resolve('/owner-review/form/review')}>Back</a>
		<SaveDraftButton onSave={saveSettingsDraft} />
		<button class="govuk-button govuk-!-margin-bottom-0" type="submit" form="workflow-settings">Continue to Flex connections</button>
	{/snippet}
</ReviewStep>

<style>
	/* Fields that belong together sit side by side, and wrap onto a new line on a narrow screen. */
	.workflow-settings__fields {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}

	.workflow-settings__fields--labelled {
		align-items: flex-start;
		gap: 20px;
	}

	/* .govuk-select has no width of its own and stretches across the column, so it is sized to its longest unit. */
	.workflow-settings__unit {
		width: auto;
		min-width: 120px;
	}
</style>
