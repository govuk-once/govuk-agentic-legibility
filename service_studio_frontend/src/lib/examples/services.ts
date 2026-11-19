import { groupByFolder, loadExamples } from './workflows';

// import.meta.glob eagerly bundles every example file at build time, so the list of examples needs no
// server round trip. The pattern only reaches one folder down, which is one folder per service.
const modules = import.meta.glob('./services/*/*.json', { eager: true, import: 'default' });

// Every service example file grouped by its folder. Exported so tests can build a broken copy of a real example.
export const serviceExampleFolders = groupByFolder(modules);

// The service examples, each checked against the schema as it is loaded.
export const serviceExamples = loadExamples(serviceExampleFolders);
