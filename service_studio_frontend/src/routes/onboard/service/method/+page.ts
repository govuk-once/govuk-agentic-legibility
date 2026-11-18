import { resolve } from '$app/paths';
import { goToChosenMethod } from '$lib/components/draft-methods';
import type { PageLoad } from './$types';

// Drafting with the assistant asks for the details of the service, which is the only choice a service offers.
export const load: PageLoad = ({ url }) => {
	goToChosenMethod(url, { automation: resolve('/onboard/service/details') });
};
