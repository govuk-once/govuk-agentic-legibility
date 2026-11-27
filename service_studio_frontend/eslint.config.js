import { includeIgnoreFile } from '@eslint/compat';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import { fileURLToPath } from 'node:url';
import ts from 'typescript-eslint';

// Files that git ignores, such as the build output and .svelte-kit, are not linted either.
const gitignorePath = fileURLToPath(new URL('./.gitignore', import.meta.url));

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	{
		languageOptions: { globals: { ...globals.browser, ...globals.node } },
		rules: {
			// TypeScript already reports names that are not defined, and does it more accurately for types.
			'no-undef': 'off',
			// Taking keys out of an object with `const { key: _unused, ...rest } = object` names the keys only so they
			// are left out of rest, so those names are not reported as unused.
			'@typescript-eslint/no-unused-vars': ['error', { ignoreRestSiblings: true }],
			// Files in src/lib are imported through the $lib alias, so every import names a file the same way from
			// wherever it is written, and a file can move without the imports inside it breaking. The one relative
			// import allowed is ./$types, the types SvelteKit generates beside each route, which has no alias.
			'no-restricted-imports': [
				'error',
				{
					patterns: [
						{
							regex: '^\\.\\.?/(?!\\$types$)',
							message: 'Import files in src/lib through $lib, such as $lib/schema/workflow/validate.'
						}
					]
				}
			]
		}
	},
	{
		// Svelte files and Svelte run files (.svelte.ts) are read by the Svelte parser, which hands the script to the
		// TypeScript parser.
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser
			}
		}
	}
);
