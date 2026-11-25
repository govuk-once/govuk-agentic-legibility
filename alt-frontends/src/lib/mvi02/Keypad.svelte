<script lang="ts">
  // Shared (src/lib/mvi/keypad-state.ts): the key layout and the letters each key types
  import { KEY_ROWS, letterLabel, type KeypadMode } from '$lib/mvi/keypad-state';
  import Icon from './Icon.svelte';

  interface Props {
    mode: KeypadMode;
    /** Whether a given key can be pressed for the current question. */
    live: (digit: string) => boolean;
    /** Keys to show as chosen, for a keyed option number. */
    chosen: string[];
    canConfirm: boolean;
    canErase: boolean;
    showModeToggle: boolean;
    /** Fades the whole keypad, for when the agent is working or listening. */
    dim?: boolean;
    onkey: (digit: string) => void;
    onerase: () => void;
    onconfirm: () => void;
    ontoggle: () => void;
  }

  let {
    mode,
    live,
    chosen,
    canConfirm,
    canErase,
    showModeToggle,
    dim = false,
    onkey,
    onerase,
    onconfirm,
    ontoggle
  }: Props = $props();

  const letterMode = $derived(mode === 'letters');

  // Buttons give up focus after a click so Enter on the keyboard confirms the answer
  // instead of pressing the last key again.
  function release(event: MouseEvent) {
    (event.currentTarget as HTMLElement).blur();
  }

  function press(event: MouseEvent, digit: string) {
    release(event);
    onkey(digit);
  }

  // In number mode a key shows its number large and bold, with its letters small beneath. In
  // letter mode it is the other way round: the letters are large and regular, the number small.
  function mainText(digit: string): string {
    return letterMode ? letterLabel(digit) : digit;
  }

  function subText(digit: string, letters: string): string {
    return letterMode ? digit : letters || ' ';
  }
</script>

<div class="mvi2-keypad" class:mvi2-keypad--dim={dim}>
  {#if showModeToggle}
    <button
      type="button"
      class="mvi2-chip mvi2-chip--toggle"
      aria-label={letterMode ? 'Switch to numbers' : 'Switch to letters'}
      onclick={(event) => {
        release(event);
        ontoggle();
      }}
    >
      {letterMode ? '123' : 'ABC'}
    </button>
  {/if}

  {#each KEY_ROWS as row, rowIndex (rowIndex)}
    <div class="mvi2-keys">
      {#each row as key (key.digit)}
        <button
          type="button"
          class="mvi2-key"
          class:mvi2-key--chosen={chosen.includes(key.digit)}
          disabled={!live(key.digit)}
          aria-label={key.letters ? `${key.digit}, ${key.letters}` : key.digit}
          onclick={(event) => press(event, key.digit)}
        >
          <span class="mvi2-key__main" class:mvi2-key__main--letters={letterMode}>{mainText(key.digit)}</span>
          <span class="mvi2-key__sub">{subText(key.digit, key.letters)}</span>
        </button>
      {/each}
    </div>
  {/each}

  <div class="mvi2-keys">
    <button
      type="button"
      class="mvi2-key"
      aria-label="Delete"
      disabled={!canErase}
      onclick={(event) => {
        release(event);
        onerase();
      }}
    >
      <Icon name="backspace" />
    </button>
    <button
      type="button"
      class="mvi2-key"
      class:mvi2-key--chosen={chosen.includes('0')}
      disabled={!live('0')}
      aria-label={letterMode ? '0, space' : '0'}
      onclick={(event) => press(event, '0')}
    >
      <span class="mvi2-key__main" class:mvi2-key__main--letters={letterMode}>{mainText('0')}</span>
      {#if letterMode}
        <span class="mvi2-key__sub">0</span>
      {/if}
    </button>
    <button
      type="button"
      class="mvi2-key mvi2-key--go"
      aria-label="Confirm"
      disabled={!canConfirm}
      onclick={(event) => {
        release(event);
        onconfirm();
      }}
    >
      <Icon name="tick" />
    </button>
  </div>
</div>
