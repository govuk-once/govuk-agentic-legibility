<script lang="ts">
  interface Step {
    key: string;
    /** "done" for a question that has been answered, "waiting" for the one waiting for you. */
    state: 'done' | 'waiting';
    title: string;
    /** A line under the title saying what happened. */
    detail: string;
    /** How long the step took, for example "2.7s". */
    time?: string;
    /** Where the step sits on the run's timeline and how much of it the step took, as percentages. */
    bar?: { left: number; width: number };
  }

  interface Props {
    steps: Step[];
  }

  let { steps }: Props = $props();
</script>

<div class="agent-run-steps">
  <!-- The column headings line up with the columns of the rows below: marker, text, bar, time. -->
  <div class="agent-run-steps__heading govuk-!-font-size-16">
    <span class="agent-run-steps__heading-marker"></span>
    <span class="agent-run-steps__heading-text">what happened</span>
    <span class="agent-run-steps__heading-track">duration</span>
    <span class="agent-run-steps__heading-time"></span>
  </div>

  {#if steps.length === 0}
    <p class="govuk-body ss-muted agent-run-steps__empty">Nothing has happened yet.</p>
  {:else}
    <ol class="agent-run-steps__list">
      {#each steps as step (step.key)}
        <li class="agent-run-steps__item" aria-current={step.state === 'waiting' ? 'step' : undefined}>
          <svg class="agent-run-steps__marker" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true" focusable="false">
            {#if step.state === 'done'}
              <circle cx="13" cy="13" r="13" fill="#00703c" />
              <path d="M7.5 13.5L11.4 17.3L18.6 9" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            {:else}
              <circle cx="13" cy="13" r="13" fill="#ffdd00" />
              <path d="M13 7V14M13 17.5V18.5" fill="none" stroke="#0b0c0c" stroke-width="2.4" stroke-linecap="round" />
            {/if}
          </svg>
          <div class="agent-run-steps__text">
            <p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-0">{step.title}</p>
            <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0">{step.detail}</p>
          </div>
          <div class="agent-run-steps__track" aria-hidden="true">
            {#if step.bar}
              <span
                class="agent-run-steps__bar"
                class:agent-run-steps__bar--waiting={step.state === 'waiting'}
                style:left="{step.bar.left}%"
                style:width="{step.bar.width}%"
              ></span>
            {/if}
          </div>
          <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0 agent-run-steps__time">{step.time ?? ''}</span>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  /* The column headings are set in a fixed-width typeface. Each has the same width as the column
     below it. */
  .agent-run-steps__heading {
    display: flex;
    gap: 16px;
    padding: 14px 20px 10px;
    border-bottom: 1px solid #ecece8;
    color: #505a5f;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
  }

  .agent-run-steps__heading-marker {
    flex: 0 0 26px;
  }

  .agent-run-steps__heading-text {
    flex: 0 1 370px;
    min-width: 0;
  }

  .agent-run-steps__heading-track {
    flex: 1 1 0;
    min-width: 120px;
  }

  .agent-run-steps__heading-time {
    flex: 0 0 56px;
  }

  .agent-run-steps__empty {
    padding: 20px;
    margin: 0;
  }

  .agent-run-steps__list {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .agent-run-steps__item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 20px;
    border-bottom: 1px solid #ecece8;
  }

  .agent-run-steps__item[aria-current='step'] {
    background-color: #fffbe0;
  }

  .agent-run-steps__marker {
    flex: 0 0 26px;
  }

  /* The text takes up to 370px and gives way on a narrow window, so the timeline gets the rest. */
  .agent-run-steps__text {
    flex: 0 1 370px;
    min-width: 0;
  }

  /* A thin grey line the width of the run, with a rounded bar on it for the step. The bar starts
     where the step began and is as long as the step took. */
  .agent-run-steps__track {
    position: relative;
    flex: 1 1 0;
    min-width: 120px;
    height: 14px;
  }

  .agent-run-steps__track::before {
    content: '';
    position: absolute;
    top: 6px;
    right: 0;
    left: 0;
    height: 1px;
    background-color: #d8d8d3;
  }

  .agent-run-steps__bar {
    position: absolute;
    top: 2px;
    height: 10px;
    border-radius: 3px;
    background-color: #1d70b8;
  }

  .agent-run-steps__bar--waiting {
    background-color: #ffdd00;
  }

  /* The time for the question waiting for you is in black, like the question itself. */
  .agent-run-steps__item[aria-current='step'] .agent-run-steps__time {
    color: #0b0c0c;
  }

  /* The time is set in a fixed-width typeface, on the right. */
  .agent-run-steps__time {
    flex: 0 0 56px;
    color: #505a5f;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
    text-align: right;
  }

  /* On a phone there is no room for the timeline, so only the text and the time are shown. */
  @media (max-width: 40em) {
    .agent-run-steps__track,
    .agent-run-steps__heading-track {
      display: none;
    }

    .agent-run-steps__text,
    .agent-run-steps__heading-text {
      flex: 1 1 0;
    }
  }
</style>
