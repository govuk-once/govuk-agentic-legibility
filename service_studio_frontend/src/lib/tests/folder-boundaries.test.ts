import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, normalize, relative, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

/*
	Keeps the folders apart so that any one editor can be deleted without breaking the others. Every file
	belongs to an area, decided by where it is, and each area may only import from the areas listed for it.
	Anything in an area that is not listed below is shared, such as the schema, graph-kit, the page
	chrome and the example loader.
*/

type Area = 'shared' | 'service' | 'form' | 'old';

// The first matching prefix decides the area. The order matters only where one prefix sits inside another.
const areaPrefixes: [string, Area][] = [
	['src/lib/service-editor/', 'service'],
	['src/routes/edit-service/', 'service'],
	['src/lib/server/onboard-service/', 'service'],
	['src/routes/onboard/service/', 'service'],
	['src/lib/form-editor/', 'form'],
	['src/routes/edit-form/', 'form'],
	['src/lib/server/onboard-form/', 'form'],
	['src/routes/onboard/form/', 'form'],
	['src/lib/components-old/', 'old'],
	['src/lib/graph-old/', 'old'],
	['src/lib/schema-old/', 'old'],
	['src/lib/examples/old/', 'old'],
	['src/lib/server/onboard-old/', 'old'],
	['src/routes/edit-old/', 'old'],
	['src/routes/onboard-old/', 'old']
];

// What each area may import from. The shared area depends on nothing but itself, and no editor depends
// on another, so each can be removed alone.
const mayImport: Record<Area, Area[]> = {
	shared: ['shared'],
	service: ['shared', 'service'],
	form: ['shared', 'form'],
	old: ['shared', 'old']
};

const root = process.cwd();
const specifier = /(\bfrom\s+|\bimport\s+|\bimport\(\s*)(['"])([^'"\n]+)\2/g;
const suffixes = ['', '.ts', '.js', '.svelte', '/index.ts'];

// Lists every code file under src, as a path from the project root with forward slashes.
function codeFiles(folder = join(root, 'src')): string[] {
	return readdirSync(folder).flatMap((name) => {
		const path = join(folder, name);
		if (statSync(path).isDirectory()) return codeFiles(path);
		return /\.(ts|js|svelte)$/.test(name) ? [relative(root, path).split(sep).join('/')] : [];
	});
}

function areaOf(file: string): Area {
	return areaPrefixes.find(([prefix]) => file.startsWith(prefix))?.[1] ?? 'shared';
}

// Finds the file that an import points at, or nothing for a package or a generated module.
function resolveImport(from: string, spec: string): string | undefined {
	const base = spec.startsWith('$lib/')
		? join('src/lib', spec.slice(5))
		: spec === '$lib'
			? 'src/lib'
			: spec.startsWith('.')
				? normalize(join(dirname(from), spec))
				: undefined;
	if (!base) return undefined;

	for (const suffix of suffixes) {
		try {
			if (statSync(join(root, base + suffix)).isFile()) return (base + suffix).split(sep).join('/');
		} catch {
			// The file does not exist with this ending, so the next ending is tried.
		}
	}
	return undefined;
}

describe('folder boundaries', () => {
	const files = codeFiles();

	it('finds the files of each area', () => {
		const areas = new Set(files.map(areaOf));
		expect([...areas].sort()).toEqual(expect.arrayContaining(['old', 'service', 'shared']));
	});

	it('lets no file import from an area it may not use', () => {
		const breaches: string[] = [];

		for (const file of files) {
			const area = areaOf(file);
			const text = readFileSync(join(root, file), 'utf8');

			for (const match of text.matchAll(specifier)) {
				const target = resolveImport(file, match[3]);
				if (!target) continue;

				const targetArea = areaOf(target);
				if (!mayImport[area].includes(targetArea)) {
					breaches.push(`${file} (${area}) imports ${target} (${targetArea})`);
				}
			}
		}

		expect(breaches).toEqual([]);
	});
});
