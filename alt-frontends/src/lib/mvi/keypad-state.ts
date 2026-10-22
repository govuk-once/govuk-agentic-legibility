// Pure logic for the /mvi keypad: digits, multi-tap letters and backspace.
// No Svelte in here so it can be tested and reused on its own.

export type KeypadMode = 'digits' | 'letters';

export interface KeyDef {
  digit: string;
  letters: string;
}

export const KEY_ROWS: KeyDef[][] = [
  [
    { digit: '1', letters: '' },
    { digit: '2', letters: 'ABC' },
    { digit: '3', letters: 'DEF' }
  ],
  [
    { digit: '4', letters: 'GHI' },
    { digit: '5', letters: 'JKL' },
    { digit: '6', letters: 'MNO' }
  ],
  [
    { digit: '7', letters: 'PQRS' },
    { digit: '8', letters: 'TUV' },
    { digit: '9', letters: 'WXYZ' }
  ]
];

/** What each key cycles through in letter mode. The digit itself comes last. */
const TAP_CYCLES: Record<string, string[]> = {
  '1': ['.', ',', "'", '-', '@', '1'],
  '2': ['A', 'B', 'C', '2'],
  '3': ['D', 'E', 'F', '3'],
  '4': ['G', 'H', 'I', '4'],
  '5': ['J', 'K', 'L', '5'],
  '6': ['M', 'N', 'O', '6'],
  '7': ['P', 'Q', 'R', 'S', '7'],
  '8': ['T', 'U', 'V', '8'],
  '9': ['W', 'X', 'Y', 'Z', '9'],
  '0': [' ', '0']
};

/** What a key shows as its main label in letter mode: its letters, or its punctuation or space. */
export function letterLabel(digit: string): string {
  if (digit === '1') return ".,'-@";
  if (digit === '0') return 'space';
  return KEY_ROWS.flat().find((key) => key.digit === digit)?.letters ?? digit;
}

/** How long, in ms, a second tap on the same key still cycles the last letter. */
export const TAP_WINDOW_MS = 800;

export interface EntryState {
  text: string;
  /** The last letter typed with a key, so a quick repeat tap can change it. */
  pending: { key: string; index: number; at: number } | null;
}

export const emptyEntry: EntryState = { text: '', pending: null };

export function pressKey(
  state: EntryState,
  key: string,
  mode: KeypadMode,
  now: number,
  maxLength: number
): EntryState {
  if (mode === 'digits') {
    if (state.text.length >= maxLength) return state;
    return { text: state.text + key, pending: null };
  }

  const cycle = TAP_CYCLES[key];
  if (!cycle) return state;

  const { pending } = state;
  if (pending && pending.key === key && now - pending.at <= TAP_WINDOW_MS && state.text.length > 0) {
    const index = (pending.index + 1) % cycle.length;
    return { text: state.text.slice(0, -1) + cycle[index], pending: { key, index, at: now } };
  }

  if (state.text.length >= maxLength) return state;
  return { text: state.text + cycle[0], pending: { key, index: 0, at: now } };
}

/** For the physical keyboard in letter mode, where a letter can be typed directly. */
export function appendChar(state: EntryState, char: string, maxLength: number): EntryState {
  if (state.text.length >= maxLength) return state;
  return { text: state.text + char.toUpperCase(), pending: null };
}

export function backspace(state: EntryState): EntryState {
  return { text: state.text.slice(0, -1), pending: null };
}
