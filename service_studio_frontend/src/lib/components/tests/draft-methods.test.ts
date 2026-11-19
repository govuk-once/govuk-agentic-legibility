import { isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { goToChosenMethod } from '../draft-methods';

// Runs the loader's step for an address and gives back where it sent the person, or nothing when it stayed.
function destination(address: string): string | undefined {
	try {
		goToChosenMethod(new URL(address, 'http://localhost'), { automation: '/onboard/form/details', existing: '/edit-form' });
		return undefined;
	} catch (thrown) {
		if (isRedirect(thrown)) return thrown.location;
		throw thrown;
	}
}

describe('goToChosenMethod', () => {
	it('sends the person to the page for the choice they made', () => {
		expect(destination('/onboard/form/method?draft-method=automation')).toBe('/onboard/form/details');
		expect(destination('/onboard/form/method?draft-method=existing')).toBe('/edit-form');
	});

	it('stays on the method page when nothing was chosen, or the choice is not offered', () => {
		expect(destination('/onboard/form/method')).toBeUndefined();
		expect(destination('/onboard/form/method?draft-method=blank')).toBeUndefined();
		expect(destination('/onboard/form/method?draft-method=toString')).toBeUndefined();
	});
});
