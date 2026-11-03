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
 * Returns every state of one type from all the example process files. The result is used to prove a
 * state schema accepts what the executor team's real workflows contain.
 */
export function exampleStatesOfType(type: string): ExampleState[] {
	return Object.values(exampleFiles).flatMap((file) =>
		Object.values(file.states ?? {}).filter((state) => state.type === type)
	);
}
