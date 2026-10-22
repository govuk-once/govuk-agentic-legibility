// Formatting helpers for the /mvi keypad readout and for what gets submitted.

const DATE_GROUPS = [2, 2, 4];

/** "21011986" shows as "21 01 1986", and part-way through as "21 01 19". */
export function formatDateDigits(digits: string): string {
  const parts: string[] = [];
  let start = 0;
  for (const size of DATE_GROUPS) {
    if (start >= digits.length) break;
    parts.push(digits.slice(start, start + size));
    start += size;
  }
  return parts.join(' ');
}

/** "21011986" becomes "21/01/1986", the shape the schemas' date patterns expect. */
export function digitsToDate(digits: string): string {
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)].filter(Boolean).join('/');
}

/** Drops the stray "|" the schemas put at the edges of lines, the same tidy-up the run events apply. */
export function tidyText(text: string): string {
  return text
    .split('\n')
    .map((line) => line.replace(/^\s*\|\s*|\s*\|\s*$/g, ''))
    .join('\n')
    .trim();
}

// The DVLA change of address journey closes with three messages. The phone shows them shorter:
// the first loses its "this can take some time" sentence, the second loses its repeated "address
// has been updated", and the thank-you line is dropped.
const CLOSING_MESSAGE_RULES: Array<[RegExp, string]> = [
  [/^Thank you\b.*$/i, ''],
  [/^Your address has been updated\.\s*/i, ''],
  [/\s*This can take some time\b.*$/i, '']
];

/** Shortens a closing message for the Call ended screen. An empty result means leave it out. */
export function tidyClosingMessage(text: string): string {
  return CLOSING_MESSAGE_RULES.reduce((result, [pattern, replacement]) => result.replace(pattern, replacement), text).trim();
}

/** Call timer text, e.g. 42 seconds becomes "00:42". */
export function clockText(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

/** "dvla.change_of_address" becomes { department: "DVLA", journey: "Change of address" }. */
export function describeWorkflow(definitionId: string): { department: string; journey: string } {
  const [department = '', ...rest] = definitionId.split('.');
  // Ids can end in a version such as ".v0.1.0", which isn't part of the journey's name.
  const versionAt = rest.findIndex((part) => /^v\d+$/.test(part));
  const nameParts = versionAt === -1 ? rest : rest.slice(0, versionAt);
  const words = nameParts.join(' ').replace(/_/g, ' ').trim();
  const journey = words ? words.charAt(0).toUpperCase() + words.slice(1) : definitionId;
  return { department: department.toUpperCase(), journey };
}
