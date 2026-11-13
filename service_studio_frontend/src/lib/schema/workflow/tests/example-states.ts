import { serviceExampleFolders } from '../../../examples/services';
import { assembleWorkflow } from '../../../examples/workflows';

/*
	Test helper that reads the two example services so each state schema can be checked against
	every real state of its type. It lives in the tests folder with the schema tests and is never imported by app code.
*/

type ExampleState = { state_type: string; [key: string]: unknown };
type ExampleFile = { states?: Record<string, ExampleState> };

// Every file in the two example services, manifests included, which is why the process files are
// picked out below by having a states key.
const exampleFiles = Object.values(serviceExampleFolders).flatMap((files) => Object.values(files)) as ExampleFile[];

/**
 * Returns every process file from the example services, which are the files that hold states. The
 * workflow manifests are left out.
 */
export function exampleProcessFiles(): unknown[] {
	return exampleFiles.filter((file) => file.states !== undefined);
}

/**
 * Returns each example service joined to its process files, in the shape that parseWorkflow reads,
 * together with the folder name. The input is unchecked, so a test can break a copy of it.
 */
export function exampleWorkflows(): { name: string; manifest: unknown; processes: Record<string, unknown> }[] {
	return Object.entries(serviceExampleFolders).map(([name, files]) => ({ name, ...assembleWorkflow(files) }));
}

/**
 * Returns every state of one type from all the example process files. The result is used to prove a
 * state schema accepts what the executor team's real workflows contain.
 */
export function exampleStatesOfType(type: string): ExampleState[] {
	return exampleFiles.flatMap((file) => Object.values(file.states ?? {}).filter((state) => state.state_type === type));
}
