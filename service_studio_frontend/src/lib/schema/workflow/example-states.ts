/*
	Test helper that reads the two example services so each state schema can be checked against
	every real state of its type. It lives beside the schema tests and is never imported by app code.
*/

type ExampleState = { type: string; [key: string]: unknown };
type ExampleFile = { states?: Record<string, ExampleState> };

// Every JSON file in the two example services, loaded as parsed JSON. The workflow manifests are
// included, which is why the states below are read with a fallback.
const exampleFiles = import.meta.glob('../../examples/new-examples/*/*.json', {
	eager: true,
	import: 'default'
}) as Record<string, ExampleFile>;

/**
 * Returns every process file from the example services, which are the files that hold states. The
 * workflow manifests are left out.
 */
export function exampleProcessFiles(): unknown[] {
	return Object.values(exampleFiles).filter((file) => file.states !== undefined);
}

/**
 * Joins the manifest of each example service to its process files, keyed by process_id, in the
 * shape of the assembled workflow. Only the folder layout is used to group the files, so this is a
 * stand in until the real loader exists.
 */
export function exampleWorkflows(): { name: string; manifest: unknown; processes: Record<string, unknown> }[] {
	const folders = new Map<string, { manifest?: unknown; processes: Record<string, unknown> }>();

	for (const [path, file] of Object.entries(exampleFiles)) {
		const [folder, fileName] = path.split('/').slice(-2);
		const entry = folders.get(folder) ?? { processes: {} };
		if (fileName === 'workflow_manifest.json') entry.manifest = file;
		else entry.processes[fileName.replace('.json', '')] = file;
		folders.set(folder, entry);
	}

	return [...folders].map(([name, { manifest, processes }]) => ({ name, manifest, processes }));
}

/**
 * Returns every state of one type from all the example process files. The result is used to prove a
 * state schema accepts what the executor team's real workflows contain.
 */
export function exampleStatesOfType(type: string): ExampleState[] {
	return Object.values(exampleFiles).flatMap((file) =>
		Object.values(file.states ?? {}).filter((state) => state.type === type)
	);
}
