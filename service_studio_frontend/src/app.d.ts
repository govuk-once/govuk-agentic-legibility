import type { WorkflowIssue } from '$lib/schema/workflow/validate';

declare global {
	namespace App {
		// A page that cannot open a workflow says why, and lists what did not match the schema when that was the reason.
		interface Error {
			message: string;
			issues?: WorkflowIssue[];
		}
	}
}

export {};
