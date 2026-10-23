// What the caller has keyed for the current question, and what that means: which view to show,
// which keys work, and what would be sent. It is the keypad logic of /mvi, gathered into one object.

// Shared (src/lib/mvi/keypad-state.ts): digits, multi-tap letters and backspace
import {
  appendChar,
  backspace,
  emptyEntry,
  pressKey,
  type EntryState,
  type KeypadMode
} from '$lib/mvi/keypad-state';
// Shared (src/lib/mvi/question.ts): turns a question into something the keypad can answer
import {
  applyChoiceDigit,
  choiceDisplay,
  choiceNumber,
  choiceSubmission,
  liveChoiceKeys,
  modelFor,
  suggestedNumbers,
  suggestedText,
  textIsComplete,
  textReadout,
  textSubmission,
  usesSingleKey,
  type QuestionModel
} from '$lib/mvi/question';
// Shared (src/lib/mvi/classify.ts): how a text question is keyed
import type { StringClassification } from '$lib/mvi/classify';
// Shared (src/lib/schema/kind.ts): the option type
import type { Choice } from '$lib/schema/kind';
// Shared (src/lib/types.ts): the question and suggestion types
import type { AwaitingInput, PrefillSuggestion } from '$lib/types';

export type CardView = 'ask' | 'digits' | 'heard' | 'file';

const CONFIRM_CHOICES: Choice[] = [
  { value: 'use', label: 'Yes, use it' },
  { value: 'key', label: "No, I'll key it in" }
];

export class KeypadSession {
  getAwaiting: () => AwaitingInput | null;

  /** A suggestion from the facts, when the agent is off. */
  suggestion = $state<PrefillSuggestion | null>(null);
  suggestionDismissed = $state(false);

  entry = $state<EntryState>(emptyEntry);
  mode = $state<KeypadMode>('letters');
  choiceEntry = $state('');
  multiNumbers = $state<number[]>([]);
  notice = $state<string | null>(null);

  awaiting = $derived.by(() => this.getAwaiting());

  baseModel = $derived.by(() => {
    const awaiting = this.awaiting;
    return awaiting ? modelFor(awaiting) : null;
  });

  /** A text answer the facts cover is first asked as a yes or no. */
  offered = $derived.by(() => {
    const model = this.baseModel;
    if (!model || this.suggestionDismissed || this.entry.text.length > 0) return null;
    return suggestedText(model, this.suggestion);
  });

  model = $derived.by((): QuestionModel | null =>
    this.offered
      ? { type: 'choice', multi: false, boolean: false, byIndex: false, choices: CONFIRM_CHOICES }
      : this.baseModel
  );

  promptText = $derived.by(() => this.awaiting?.prompt ?? '');
  questionText = $derived.by(() => (this.offered ? `Do you want to use ${this.offered}?` : this.promptText));

  choices = $derived.by(() => (this.model?.type === 'choice' ? this.model.choices : null));
  choiceCount = $derived.by(() => this.choices?.length ?? 0);

  highlighted = $derived.by((): number[] => {
    const model = this.model;
    if (model?.type !== 'choice') return [];
    if (model.multi) return this.multiNumbers;
    const number = choiceNumber(this.choiceEntry, this.choiceCount);
    return number ? [number] : [];
  });

  suggestedNums = $derived.by((): number[] => {
    if (this.offered) return [1];
    return this.baseModel ? suggestedNumbers(this.baseModel, this.suggestion) : [];
  });

  /** The question view shows until the first key is pressed, then an answer view. */
  inAnswer = $derived.by(() => {
    const model = this.model;
    if (model?.type === 'choice') return this.choiceEntry !== '' || this.multiNumbers.length > 0;
    if (model?.type === 'text') return this.entry.text.length > 0;
    return false;
  });

  view = $derived.by((): CardView => {
    const model = this.model;
    if (model?.type === 'file') return 'file';
    if (!this.inAnswer) return 'ask';
    if (model?.type === 'text' && model.classification.format !== 'text') return 'digits';
    return 'heard';
  });

  /** What the big readout shows. */
  readout = $derived.by(() => {
    const model = this.model;
    if (model?.type === 'text') return textReadout(model.classification, this.entry.text);
    if (model?.type === 'choice') return this.highlighted.join(', ');
    return '';
  });

  /** What "The service heard" shows, as if it had been spoken. */
  heard = $derived.by(() => {
    const model = this.model;
    if (model?.type === 'choice' && this.highlighted.length > 0) return choiceDisplay(model, this.highlighted);
    if (model?.type === 'text') return textReadout(model.classification, this.entry.text);
    return '';
  });

  /** The small line under a date's digits. */
  hint = $derived.by(() => {
    const model = this.model;
    return model?.type === 'text' && model.classification.format === 'date' ? 'Day · Month · Year' : '';
  });

  canConfirm = $derived.by(() => {
    const model = this.model;
    if (!this.awaiting || !model) return false;
    if (model.type === 'choice') {
      return this.highlighted.length > 0 || (!this.inAnswer && this.suggestedNums.length > 0);
    }
    if (model.type === 'text') return this.textFits(model.classification, this.entry.text);
    return false;
  });

  /**
   * The journey's own message about the format, once enough has been keyed that the tick should
   * have lit up but didn't. Without it a rejected answer, such as a National Insurance number with
   * a letter the pattern doesn't allow, just leaves the tick dull with no hint why.
   */
  problem = $derived.by((): string | null => {
    const model = this.model;
    if (model?.type !== 'text' || this.entry.text.length < 5) return null;
    if (this.textFits(model.classification, this.entry.text)) return null;
    return this.awaiting?.schema.invalid_message ?? "That doesn't look right yet.";
  });

  canErase = $derived.by(() => this.inAnswer);

  showModeToggle = $derived.by(() => this.model?.type === 'text' && this.model.classification.format === 'text');

  /** Choice questions always use the number keys; only text questions can show letters. */
  keypadMode = $derived.by((): KeypadMode => (this.model?.type === 'text' ? this.mode : 'digits'));

  /** Keys lit on the keypad: the keyed option, or the suggested one when nothing has been keyed. */
  chosenKeys = $derived.by((): string[] => {
    if (this.model?.type !== 'choice') return [];
    return (this.highlighted.length > 0 ? this.highlighted : this.suggestedNums).map(String);
  });

  constructor(getAwaiting: () => AwaitingInput | null) {
    this.getAwaiting = getAwaiting;
  }

  // Some answers, such as a National Insurance number, are usually written with spaces but the
  // journey's pattern doesn't allow them. If the text only fits without its spaces, those are dropped.
  private textValue(classification: StringClassification, text: string): string {
    const plain = textSubmission(classification, text);
    if (textIsComplete(classification, text)) return plain;
    const squashed = text.replace(/\s+/g, '');
    return squashed !== text && textIsComplete(classification, squashed) ? squashed : plain;
  }

  private textFits(classification: StringClassification, text: string): boolean {
    if (textIsComplete(classification, text)) return true;
    const squashed = text.replace(/\s+/g, '');
    return squashed !== text && textIsComplete(classification, squashed);
  }

  isLive(digit: string): boolean {
    const model = this.model;
    if (!model) return false;
    if (model.type === 'choice') {
      // 0 is "Speak to a person" when every option fits on one key. It is shown but does nothing.
      return liveChoiceKeys(this.choiceCount).has(digit) || (digit === '0' && usesSingleKey(this.choiceCount));
    }
    return model.type === 'text';
  }

  clear() {
    this.entry = emptyEntry;
    this.choiceEntry = '';
    this.multiNumbers = [];
    this.notice = null;
  }

  /** A new question starts clean. */
  reset() {
    this.clear();
    this.suggestion = null;
    this.suggestionDismissed = false;
    const awaiting = this.awaiting;
    if (awaiting) {
      const next = modelFor(awaiting);
      if (next.type === 'text') this.mode = next.classification.startMode;
    }
  }

  press(digit: string) {
    const model = this.model;
    if (!model) return;
    this.notice = null;

    if (model.type === 'choice') {
      if (digit === '0' && usesSingleKey(this.choiceCount)) {
        this.notice = "Speaking to a person isn't available in this demo.";
        return;
      }
      if (!liveChoiceKeys(this.choiceCount).has(digit)) return;
      if (model.multi) {
        const number = Number(digit);
        this.multiNumbers = this.multiNumbers.includes(number)
          ? this.multiNumbers.filter((existing) => existing !== number)
          : [...this.multiNumbers, number].sort((a, b) => a - b);
      } else {
        this.choiceEntry = applyChoiceDigit(this.choiceEntry, digit, this.choiceCount);
      }
    } else if (model.type === 'text') {
      this.entry = pressKey(this.entry, digit, this.mode, Date.now(), model.classification.maxLength);
    }
  }

  /** A letter, digit or mark typed on the physical keyboard in letter mode. */
  typeLetter(char: string) {
    const model = this.model;
    if (model?.type !== 'text' || this.mode !== 'letters') return;
    this.entry = appendChar(this.entry, char, model.classification.maxLength);
  }

  erase() {
    const model = this.model;
    if (!model) return;
    this.notice = null;
    if (model.type === 'choice') {
      if (model.multi) this.multiNumbers = this.multiNumbers.slice(0, -1);
      else this.choiceEntry = this.choiceEntry.slice(0, -1);
    } else if (model.type === 'text') {
      this.entry = backspace(this.entry);
    }
  }

  toggleMode() {
    this.mode = this.mode === 'digits' ? 'letters' : 'digits';
    this.entry = { ...this.entry, pending: null };
  }

  /**
   * What pressing the tick would send, or null when it only changes what is on screen (turning
   * down a suggestion). `confirmed` is true for answers picked from options.
   */
  takeAnswer(): { value: unknown; display: string; confirmed: boolean } | null {
    const model = this.model;
    if (!this.canConfirm || !model) return null;

    if (model.type === 'choice') {
      const numbers = this.highlighted.length > 0 ? this.highlighted : this.suggestedNums;
      const offered = this.offered;
      if (offered) {
        if (numbers[0] === 1) return { value: offered, display: offered, confirmed: true };
        this.suggestionDismissed = true;
        this.clear();
        return null;
      }
      return {
        value: choiceSubmission(model, numbers),
        display: choiceDisplay(model, numbers),
        confirmed: true
      };
    }

    if (model.type === 'text') {
      const value = this.textValue(model.classification, this.entry.text);
      return { value, display: value, confirmed: false };
    }
    return null;
  }
}
