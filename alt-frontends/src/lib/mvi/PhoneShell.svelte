<script lang="ts">
  import type { Snippet } from 'svelte';
  import CallBar from './CallBar.svelte';

  interface Props {
    /** The call bar's right-hand text. Both are left out on the start screen. */
    department?: string;
    clock?: string;
    /** Changes whenever the screen changes, so the scrolling area starts back at the top. */
    scrollKey?: string;
    /** Keep the screen at the top instead of centred, for lists such as the journey cards. */
    top?: boolean;
    children: Snippet;
    /** The grey keypad area under the screen. */
    keypad?: Snippet;
    /** Set to false when the keypad has nothing to show, so its grey area isn't left behind. */
    showKeypad?: boolean;
    /** Buttons pinned under the screen, on the plain background. */
    actions?: Snippet;
    /** Something laid over the whole phone, such as the add-context sheet. */
    overlay?: Snippet;
  }

  let {
    department = '',
    clock = '',
    scrollKey = '',
    top = false,
    children,
    keypad,
    showKeypad = true,
    actions,
    overlay
  }: Props = $props();

  // Runs again whenever the screen changes, so the scrolling area starts back at the top.
  function startAtTop(node: HTMLElement) {
    void scrollKey;
    node.scrollTop = 0;
  }
</script>

<section aria-label="Phone">
  <CallBar {department} {clock} />
  <div class="ss-panel" {@attach startAtTop}>
    <div data-top={top ? '' : undefined}>
      {@render children()}
    </div>
  </div>
  {#if keypad && showKeypad}
    <div class="ss-stat">
      {@render keypad()}
    </div>
  {/if}
  {#if actions}
    <div class="govuk-!-padding-4">
      {@render actions()}
    </div>
  {/if}
  {#if overlay}
    {@render overlay()}
  {/if}
</section>

<style>
  /* An iPhone Pro Max sized frame (440 x 956), centred on the page. The width is fixed. The height is 956 but never taller than the window, so on a short
     window the phone is shorter rather than the page scrolling. When a screen has more content
     than room, the content scrolls inside the phone, not the page. It is positioned so that
     anything laid over the phone, such as the add-context sheet, stays inside it. */
  section {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 440px;
    max-width: 100%;
    height: min(956px, calc(100dvh - 78px));
    min-height: 560px;
    margin-inline: auto;
    overflow: hidden;
    /* A fine grey edge so the phone doesn't get lost against the white page. */
    box-sizing: border-box;
    border: 1px solid #b1b4b6;
  }

  /* The screen sits centred between the bar and the keypad, as in the design. If a screen is
     taller than the room it simply starts at the top and scrolls. */
  .ss-panel {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    /* The phone has its own outer edge, so the screen area needs no box of its own. */
    border: 0;
  }

  .ss-panel > div {
    margin-block: auto;
  }

  .ss-panel > div[data-top] {
    margin-block: 0;
  }

  .ss-stat {
    flex: 0 0 auto;
  }
</style>
