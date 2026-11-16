import { placeholderExecutor, placeholderNamespace, placeholderOwner } from '$lib/schema/workflow/placeholders';
import type { Duration } from '$lib/schema/workflow/primitives';
import type { Process } from '$lib/schema/workflow/process';
import { currentSchemaVersion, type Manifest, type Workflow } from '$lib/schema/workflow/workflow';
import { isAllowedLink } from './allowed-link-domains';
import { firstVersion, slugOf, type OnboardDetails } from './onboard-details';

/*
	Wraps the process that the model generated into a whole workflow that an editor can open. The model is only
	asked for the journey itself. Everything else is decided here, because the model has no way of knowing it and
	a guess would look like a real value: the ids, the owner and the executor settings. Each of those is a
	placeholder that a person replaces at a later review, and each is a valid value, so the workflow can be checked
	and opened straight away. A service and a form are wrapped in the same way, so this is kept here and not with
	either one.
*/

// What differs between one kind of draft and another: the defaults its calls use, and how long a whole run may last.
export type DraftSettings = { defaults: Manifest['defaults']; runTimeout: Duration };

/**
 * Wraps a generated process into a workflow with a manifest. The process is given the id and version that the
 * manifest lists, and the links the person gave that are on the list of readable sites become its sources. The
 * manifest holds the placeholders for the owner and the executor settings, with the defaults and the run limit
 * of this kind of draft. The process that is given in is never changed.
 */
export function buildDraftWorkflow(generated: Process, details: OnboardDetails, settings: DraftSettings): Workflow {
	const slug = slugOf(details.name);

	// Only a link on the list of sites the assistant may read is kept, because a page that was not read did not
	// inform the draft. When no usable link was given, whatever sources the process already had are kept.
	const links = details.links.filter((link) => isAllowedLink(link));
	const process: Process = {
		...generated,
		process_id: slug,
		version: firstVersion,
		...(links.length > 0 ? { source: links } : {})
	};

	return {
		manifest: {
			workflow_id: slug,
			schema: currentSchemaVersion,
			id: `${placeholderNamespace}.${slug}`,
			version: firstVersion,
			...placeholderOwner,
			description: details.description,
			state: 'draft',
			entry: slug,
			executor: placeholderExecutor(slug, settings.runTimeout),
			defaults: settings.defaults,
			processes: [{ process_id: slug, version: firstVersion }]
		},
		processes: { [slug]: process }
	};
}
