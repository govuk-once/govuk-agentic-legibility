import { describe, expect, it } from 'vitest';
import { agentNotesLimit, ownerDetailsOf, ownerDetailsProblems, withOwnerDetails, type OwnerDetails } from '../owner-details';
import { placeholderOwner } from '../placeholders';
import { manifestSchema, type Manifest } from '../workflow';

// Only the keys the owner details read and write. The cast is needed because a test gives only the keys it uses.
const manifestWith = (keys: Partial<Manifest>) => keys as Manifest;

const filledIn: OwnerDetails = {
	firstName: 'Sam',
	lastName: 'Jones',
	department: 'dvla',
	email: 'sam.jones@example.gov.uk',
	agentPage: 'https://www.gov.uk/renew-driving-licence',
	agentNotes: 'Speak plainly.'
};

describe('ownerDetailsOf', () => {
	it('reads the department from the owner, the email from the contact and the rest from the notes', () => {
		const manifest = manifestWith({
			owner: 'dvla',
			contact: 'sam.jones@example.gov.uk',
			metadata: { owner_first_name: 'Sam', owner_last_name: 'Jones', agent_page: 'https://www.gov.uk/renew-driving-licence', agent_notes: 'Speak plainly.' }
		});
		expect(ownerDetailsOf(manifest)).toEqual(filledIn);
	});

	it('reads the placeholder owner and contact of a draft as empty', () => {
		expect(ownerDetailsOf(manifestWith({ ...placeholderOwner }))).toEqual({
			firstName: '',
			lastName: '',
			department: '',
			email: '',
			agentPage: '',
			agentNotes: ''
		});
	});

	it('reads a missing owner, contact and metadata as empty', () => {
		expect(ownerDetailsOf(manifestWith({ owner: null, contact: null, metadata: null })).department).toBe('');
	});
});

describe('withOwnerDetails', () => {
	it('writes the department, the email and the notes, and keeps every other note', () => {
		const manifest = withOwnerDetails(manifestWith({ metadata: { description: 'About the form' } }), filledIn);
		expect(manifest.owner).toBe('dvla');
		expect(manifest.contact).toBe('sam.jones@example.gov.uk');
		expect(manifest.metadata).toEqual({
			description: 'About the form',
			owner_first_name: 'Sam',
			owner_last_name: 'Jones',
			agent_page: 'https://www.gov.uk/renew-driving-licence',
			agent_notes: 'Speak plainly.'
		});
	});

	it('removes the agent notes when their fields are empty', () => {
		const manifest = withOwnerDetails(
			manifestWith({ metadata: { agent_page: 'https://www.gov.uk/old', agent_notes: 'Old notes' } }),
			{ ...filledIn, agentPage: ' ', agentNotes: '' }
		);
		expect(manifest.metadata).toEqual({ owner_first_name: 'Sam', owner_last_name: 'Jones' });
	});

	it('trims the spaces around each value', () => {
		const manifest = withOwnerDetails(manifestWith({}), { ...filledIn, department: '  dvla ', firstName: ' Sam ' });
		expect(manifest.owner).toBe('dvla');
		expect(manifest.metadata?.owner_first_name).toBe('Sam');
	});

	it('gives values that the manifest schema accepts', () => {
		const owner = manifestSchema.shape.owner;
		const contact = manifestSchema.shape.contact;
		const manifest = withOwnerDetails(manifestWith({}), filledIn);
		expect(owner.safeParse(manifest.owner).success).toBe(true);
		expect(contact.safeParse(manifest.contact).success).toBe(true);
	});
});

describe('ownerDetailsProblems', () => {
	it('has nothing to say about details that are filled in', () => {
		expect(ownerDetailsProblems(filledIn)).toEqual([]);
	});

	it('asks for the names, the department and the email, in the order they are shown', () => {
		const empty = { firstName: '', lastName: '', department: ' ', email: '', agentPage: '', agentNotes: '' };
		expect(ownerDetailsProblems(empty).map((problem) => problem.field)).toEqual(['firstName', 'lastName', 'department', 'email']);
	});

	it('asks for an email address in the correct format', () => {
		expect(ownerDetailsProblems({ ...filledIn, email: 'sam.jones' })).toEqual([
			{ field: 'email', message: 'Enter an email address in the correct format, like name@example.gov.uk' }
		]);
	});

	it('asks for a page for the agent that is a web address', () => {
		expect(ownerDetailsProblems({ ...filledIn, agentPage: 'renew driving licence' }).map((problem) => problem.field)).toEqual([
			'agentPage'
		]);
	});

	it('refuses notes for the agent that are longer than the limit', () => {
		const notes = 'a'.repeat(agentNotesLimit + 1);
		expect(ownerDetailsProblems({ ...filledIn, agentNotes: notes })).toEqual([
			{ field: 'agentNotes', message: 'Notes for the agent must be 4,000 characters or fewer' }
		]);
	});
});
