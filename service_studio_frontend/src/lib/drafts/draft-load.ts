import type { WorkflowIssue } from '$lib/schema/workflow/validate';
import type { Workflow } from '$lib/schema/workflow/workflow';

// What opening a draft for an editor gives back: the workflow when it passes the schema check, or the reason it could
// not be opened. The page that shows a draft problem reads it, so the form editor and the service editor describe a
// missing or broken draft the same way.
export type DraftLoad =
	| { ok: true; workflow: Workflow }
	| { ok: false; reason: 'missing' }
	| { ok: false; reason: 'invalid'; issues: WorkflowIssue[] };
