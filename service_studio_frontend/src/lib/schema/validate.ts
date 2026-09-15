import { serviceSchema, type Service } from './service';

// One issue from a failed validation, flattened to a dotted path and a message so it can be listed
// directly in a GOV.UK error summary.
export type ServiceIssue = { path: string; message: string };

export type ServiceValidation =
	| { ok: true; service: Service }
	| { ok: false; issues: ServiceIssue[] };

/**
 * Validates the input against the service schema. Returns the typed service on success, or a flat list
 * of path and message issues on failure.
 */
export function parseService(input: unknown): ServiceValidation {
	const result = serviceSchema.safeParse(input);

	if (result.success) {
		return { ok: true, service: result.data };
	}

	return {
		ok: false,
		issues: result.error.issues.map((issue) => ({
			path: issue.path.length ? issue.path.join('.') : '(root)',
			message: issue.message
		}))
	};
}
