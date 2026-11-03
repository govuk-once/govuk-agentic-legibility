/**
 * Turns a state's code, such as "confirm_intent" or "uploadPhoto", into a short readable label such
 * as "Confirm intent" or "Upload photo". A step with no title and no text of its own falls back to
 * this, so the graph never shows a raw code to the person reading it.
 *
 * Words are split at underscores, hyphens, dots and camel case boundaries, then written in lower
 * case with a capital on the first word only. A word that is already all capitals, such as "DVLA" or
 * "MATB1", is kept as it is, because lower casing an acronym would change its meaning.
 */
export function tidyCode(code: string): string {
	const words = code
		.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
		.split(/[\s_.-]+/)
		.filter(Boolean)
		.map((word) => (isAcronym(word) ? word : word.toLowerCase()));

	if (words.length === 0) return '';

	words[0] = words[0].charAt(0).toUpperCase() + words[0].slice(1);
	return words.join(' ');
}

/**
 * Tells whether a word is written in capitals with more than one character, which marks it as an
 * acronym or a reference code that should keep its capitals.
 */
function isAcronym(word: string): boolean {
	return word.length > 1 && /[A-Z]/.test(word) && word === word.toUpperCase();
}
