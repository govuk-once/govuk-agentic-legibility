<script lang="ts">
  import { KEY_ROWS, letterLabel, type KeypadMode } from './keypad-state';

  interface Props {
    mode: KeypadMode;
    /** Whether a given key can be pressed for the current question. */
    live: (digit: string) => boolean;
    /** Keys to show as chosen, for a keyed option number. */
    chosen: string[];
    canConfirm: boolean;
    canErase: boolean;
    showModeToggle: boolean;
    onkey: (digit: string) => void;
    onerase: () => void;
    onconfirm: () => void;
    ontoggle: () => void;
  }

  let { mode, live, chosen, canConfirm, canErase, showModeToggle, onkey, onerase, onconfirm, ontoggle }: Props =
    $props();

  // Buttons give up focus after a click so Enter on the keyboard confirms the answer
  // instead of pressing the last key again.
  function release(event: MouseEvent) {
    (event.currentTarget as HTMLElement).blur();
  }

  function press(event: MouseEvent, digit: string) {
    release(event);
    onkey(digit);
  }

  // In number mode a key shows its number large and bold, with its letters small beneath.
  // In letter mode it is the other way round: the letters are large, in a regular weight, with
  // the number small beneath.
  const letterMode = $derived(mode === 'letters');

  function mainText(digit: string): string {
    return letterMode ? letterLabel(digit) : digit;
  }

  function subText(digit: string, letters: string): string {
    return letterMode ? digit : letters || ' ';
  }

  const mainClass = $derived(
    letterMode
      ? 'govuk-!-display-block govuk-!-font-size-19 govuk-!-font-weight-regular'
      : 'govuk-!-display-block govuk-!-font-size-24 govuk-!-font-weight-bold'
  );
</script>

{#if showModeToggle}
  <button
    type="button"
    class="govuk-button govuk-button--secondary govuk-!-margin-bottom-2"
    aria-label={mode === 'digits' ? 'Switch to letters' : 'Switch to numbers'}
    onclick={(event) => {
      release(event);
      ontoggle();
    }}
  >
    {mode === 'digits' ? 'ABC' : '123'}
  </button>
{/if}

{#each KEY_ROWS as row, rowIndex (rowIndex)}
  <div class="govuk-grid-row">
    {#each row as key (key.digit)}
      <div class="govuk-grid-column-one-third">
        <button
          type="button"
          class="govuk-button govuk-button--secondary govuk-!-width-full govuk-!-margin-bottom-2"
          class:ss-card--selected={chosen.includes(key.digit)}
          disabled={!live(key.digit)}
          aria-label={key.letters ? `${key.digit}, ${key.letters}` : key.digit}
          onclick={(event) => press(event, key.digit)}
        >
          <span class={mainClass}>{mainText(key.digit)}</span>
          <span class="govuk-!-display-block govuk-!-font-size-14 govuk-!-font-weight-regular ss-muted"
            >{subText(key.digit, key.letters)}</span
          >
        </button>
      </div>
    {/each}
  </div>
{/each}

<div class="govuk-grid-row">
  <div class="govuk-grid-column-one-third">
    <button
      type="button"
      class="govuk-button govuk-button--secondary govuk-!-width-full govuk-!-margin-bottom-0"
      aria-label="Delete"
      disabled={!canErase}
      onclick={(event) => {
        release(event);
        onerase();
      }}
    >
      <svg width="24" height="17" viewBox="0 0 24 17" xmlns="http://www.w3.org/2000/svg" focusable="false">
        <path d="M8 1 H22 V16 H8 L1 8.5 Z" fill="none" stroke="currentColor" stroke-width="1.6" />
        <path d="M12 5.5 L18 11.5 M18 5.5 L12 11.5" fill="none" stroke="currentColor" stroke-width="1.6" />
      </svg>
    </button>
  </div>
  <div class="govuk-grid-column-one-third">
    <button
      type="button"
      class="govuk-button govuk-button--secondary govuk-!-width-full govuk-!-margin-bottom-0"
      class:ss-card--selected={chosen.includes('0')}
      disabled={!live('0')}
      aria-label={mode === 'letters' ? '0, space' : '0'}
      onclick={(event) => press(event, '0')}
    >
      <span class={mainClass}>{mainText('0')}</span>
      <span class="govuk-!-display-block govuk-!-font-size-14 govuk-!-font-weight-regular ss-muted"
        >{subText('0', '')}</span
      >
    </button>
  </div>
  <div class="govuk-grid-column-one-third">
    <button
      type="button"
      class="govuk-button govuk-!-width-full govuk-!-margin-bottom-0"
      aria-label="Confirm"
      disabled={!canConfirm}
      onclick={(event) => {
        release(event);
        onconfirm();
      }}
    >
      <svg width="22" height="17" viewBox="0 0 22 17" xmlns="http://www.w3.org/2000/svg" focusable="false">
        <path d="M2 9 L8 15 L20 2" fill="none" stroke="currentColor" stroke-width="2.5" />
      </svg>
    </button>
  </div>
</div>

<style>
  /* GOV.UK's grid stacks its columns below 641px, which would turn the keypad into one tall
     column on a narrow window. This keeps each row of three keys side by side. */
  .govuk-grid-row {
    display: flex;
  }

  .govuk-grid-row > .govuk-grid-column-one-third {
    flex: 1 1 0;
    min-width: 0;
    width: auto;
  }
</style>
