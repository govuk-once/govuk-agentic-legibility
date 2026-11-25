<script lang="ts">
  // Shared (src/lib/agentic/event-tags.ts): how each kind of event is labelled and coloured
  import { awaitingToken, categoryText, tagColour, type RunEventLine } from '$lib/agentic/event-tags';

  interface Props {
    events: RunEventLine[];
  }

  let { events }: Props = $props();

  // Only the latest few events are shown here, to keep the side column short.
  const SHOWN = 8;
  const latest = $derived(events.slice(-SHOWN));
</script>

<section aria-labelledby="agent-activity-title">
  <h2 id="agent-activity-title" class="govuk-heading-s agent-activity__heading">Activity</h2>

  {#each latest as line, index (events.length - latest.length + index)}
    {@const token = awaitingToken(line.summary)}
    <div class="ss-card agent-activity__row">
      <span class="agent-activity__tag"><span class="govuk-tag {tagColour(line)}">{categoryText(line.category)}</span></span>
      <span class="govuk-body govuk-!-font-size-16 govuk-!-margin-0">
        {#if token}
          <strong>Awaiting input</strong> [{token}]
        {:else}
          {line.summary}
        {/if}
      </span>
    </div>
  {:else}
    <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-top-2">No activity yet.</p>
  {/each}

  {#if events.length > SHOWN}
    <p class="govuk-body govuk-!-font-size-16 ss-muted govuk-!-margin-top-2 govuk-!-margin-bottom-0">
      Showing the latest {SHOWN} of {events.length} events.
    </p>
  {/if}
</section>

<style>
  /* The heading is underlined in blue, and the rows sit flush with it instead of padded like cards. */
  .agent-activity__heading {
    margin-bottom: 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #1d70b8;
  }

  .agent-activity__row {
    align-items: flex-start;
    gap: 12px;
    padding: 10px 0;
  }

  /* A fixed column so the words line up whichever tag is beside them. */
  .agent-activity__tag {
    flex: 0 0 96px;
  }
</style>
