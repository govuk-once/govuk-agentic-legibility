import { z } from 'zod';
import { placeholderOwner } from '$lib/schema/workflow/placeholders';
import type { Manifest } from '$lib/schema/workflow/workflow';

/*
	The details an owner gives at the owner review, and where each is kept in the workflow manifest. The manifest
	names its owner as a department, as the examples do, and gives one email address as the contact. The person's names
	and the context for the agent have no key of their own, so they are kept as notes in the manifest metadata. The
	first and last names are kept apart, because a full name cannot be split again reliably.
*/

export interface OwnerDetails {
	// The person accountable for the form, kept as the owner_first_name and owner_last_name notes.
	firstName: string;
	lastName: string;
	// The department that owns the form, kept as the manifest owner.
	department: string;
	// Where the owner is contacted, kept as the manifest contact.
	email: string;
	// A web page the agent reads for background, kept as the agent_page note.
	agentPage: string;
	// Notes the agent can use on every call, kept as the agent_notes note.
	agentNotes: string;
}

export type OwnerDetailsField = keyof OwnerDetails;

// One problem with the details, named by the field it belongs to so a page can show it beside that field.
export interface OwnerDetailsProblem {
	field: OwnerDetailsField;
	message: string;
}

// The longest the notes for the agent can be, so they stay short enough to read on every call.
export const agentNotesLimit = 4000;

// Reads a note that is text, or gives an empty string when it is missing or not text.
function textNote(manifest: Manifest, key: string): string {
	const note = manifest.metadata?.[key];
	return typeof note === 'string' ? note : '';
}

/**
 * Reads the owner details from a manifest. A draft holds placeholders for the owner and the contact until they are
 * given here, and those are read as empty so the owner is asked for real values.
 */
export function ownerDetailsOf(manifest: Manifest): OwnerDetails {
	const owner = manifest.owner ?? '';
	const contact = manifest.contact ?? '';
	return {
		firstName: textNote(manifest, 'owner_first_name'),
		lastName: textNote(manifest, 'owner_last_name'),
		department: owner === placeholderOwner.owner ? '' : owner,
		email: contact === placeholderOwner.contact ? '' : contact,
		agentPage: textNote(manifest, 'agent_page'),
		agentNotes: textNote(manifest, 'agent_notes')
	};
}

/**
 * Writes the owner details into a copy of a manifest. Every other note in the metadata is kept. The agent context is
 * optional, so an empty field removes its note rather than saving an empty one.
 */
export function withOwnerDetails(manifest: Manifest, details: OwnerDetails): Manifest {
	// The agent notes are taken out first, so a field that is now empty no longer has a note.
	const notes = { ...manifest.metadata };
	delete notes.agent_page;
	delete notes.agent_notes;
	return {
		...manifest,
		owner: details.department.trim(),
		contact: details.email.trim(),
		metadata: {
			...notes,
			owner_first_name: details.firstName.trim(),
			owner_last_name: details.lastName.trim(),
			...(details.agentPage.trim() && { agent_page: details.agentPage.trim() }),
			...(details.agentNotes.trim() && { agent_notes: details.agentNotes.trim() })
		}
	};
}

/**
 * Lists what must be put right before the details can be saved, in the order the fields are shown. The names, the
 * department and the email are required, because the owner signs off the form and is told when it changes. The agent
 * context is optional, but a page must be a web address and the notes must fit the limit.
 */
export function ownerDetailsProblems(details: OwnerDetails): OwnerDetailsProblem[] {
	const problems: OwnerDetailsProblem[] = [];
	if (!details.firstName.trim()) problems.push({ field: 'firstName', message: 'Enter the first name of the owner' });
	if (!details.lastName.trim()) problems.push({ field: 'lastName', message: 'Enter the last name of the owner' });
	if (!details.department.trim()) problems.push({ field: 'department', message: 'Enter the department that owns the form' });
	if (!details.email.trim()) problems.push({ field: 'email', message: 'Enter the email address of the owner' });
	else if (!z.email().safeParse(details.email.trim()).success) {
		problems.push({ field: 'email', message: 'Enter an email address in the correct format, like name@example.gov.uk' });
	}
	if (details.agentPage.trim() && !z.url({ protocol: /^https?$/ }).safeParse(details.agentPage.trim()).success) {
		problems.push({ field: 'agentPage', message: 'Enter a web address in the correct format, like https://www.gov.uk/renew-driving-licence' });
	}
	if (details.agentNotes.length > agentNotesLimit) {
		problems.push({ field: 'agentNotes', message: `Notes for the agent must be ${agentNotesLimit.toLocaleString('en-GB')} characters or fewer` });
	}
	return problems;
}
