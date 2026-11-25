import type { Manifest } from '$lib/schema/workflow/workflow';
import type { WorkflowIssue } from '$lib/schema/workflow/validate';

declare global {
	namespace App {
		// A page that cannot open a workflow says why, and lists what did not match the schema when that was the reason.
		interface Error {
			message: string;
			issues?: WorkflowIssue[];
		}

		// What Publish passes to the page after it, because the draft the form came from is deleted when it is published.
		interface PageState {
			published?: Pick<Manifest, 'description' | 'version' | 'contact'>;
		}
	}
}

export {};
