<script lang="ts">
  interface Step {
    key: string;
    /** "done" for a question that has been answered, "waiting" for the one waiting for you. */
    state: 'done' | 'waiting';
    title: string;
    /** A line under the title saying what happened. */
    detail: string;
  }

  interface Props {
    steps: Step[];
  }

  let { steps }: Props = $props();
</script>

<div class="agent-run-steps">
  <p class="agent-run-steps__heading govuk-!-font-size-16 govuk-!-margin-0">what happened</p>

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
          <div>
            <p class="govuk-body govuk-!-font-weight-bold govuk-!-margin-0">{step.title}</p>
            <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-0">{step.detail}</p>
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  /* The column heading is set in a fixed-width typeface, as in the design. */
  .agent-run-steps__heading {
    padding: 14px 20px 10px;
    border-bottom: 1px solid #ecece8;
    color: #505a5f;
    font-family: ui-monospace, 'IBM Plex Mono', monospace;
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
    align-items: flex-start;
    gap: 16px;
    padding: 14px 20px;
    border-bottom: 1px solid #ecece8;
  }

  .agent-run-steps__item[aria-current='step'] {
    background-color: #fffbe0;
  }

  .agent-run-steps__marker {
    flex: 0 0 26px;
    margin-top: 2px;
  }
</style>
