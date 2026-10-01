<script lang="ts">
  import type { StepNodeData } from './types';

  // Read-only: unlike service_studio_frontend's StepNode.svelte, this has no click/select handling — the
  // dashboard only ever highlights the state the run is currently awaiting, it never lets a citizen pick
  // a different one. The kind badge (INPUT/CALL/CHOICE/...) is shown for auditability, since there is no
  // step editor here to look the state up in.
  let { data, ariaLabel }: { data: StepNodeData; ariaLabel: string } = $props();
</script>

<div
  class="journey-step-node"
  class:journey-step-node--current={data.status === 'current'}
  role="img"
  aria-label={ariaLabel}
  style:width="{data.width}px"
  style:height="{data.height}px"
>
  <span class="journey-step-node__kind">{data.kind}</span>
  <h3 class="govuk-heading-s govuk-!-margin-bottom-0 journey-step-node__title">
    {data.title}
  </h3>
</div>

<style>
  .journey-step-node {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    width: 100%;
    margin: 0;
    padding: 10px 15px;
    background-color: #ffffff;
    border: 1px solid #b1b4b6;
    font-family: 'GDS Transport', arial, sans-serif;
    text-align: left;
  }

  .journey-step-node__kind {
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #505a5f;
  }

  /* Extra rule for long titles, not the primary sizing mechanism: the computed height in node-sizing.ts
    already fits up to this many lines, so this only ever clips a title longer than that estimate
    expected. */
  .journey-step-node__title {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;
  }

  .journey-step-node--current {
    border: 3px solid #1d70b8;
  }
</style>
