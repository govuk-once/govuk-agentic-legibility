<h1 class="govuk-heading-l">Alternative Frontends</h1>

<p class="govuk-body">
  Four interaction styles, one Temporal-backed workflow contract. <code>/web</code> is
  the deterministic mode — Temporal stays authoritative, with an optional LLM
  suggesting field values from notes you provide.
</p>

<div class="front-doors">
  {#each [
    { href: '/web', name: '/web', description: 'Form-driven, LLM-assisted pre-fill' },
    { href: '/chat', name: '/chat', description: 'Natural-language, agent-mediated' },
    { href: '/agentic', name: '/agentic', description: 'Autonomous, profile-driven' },
    { href: '/voice', name: '/voice', description: 'Speech in, speech out, agent-mediated' }
  ] as door (door.href)}
    <div class="ss-panel front-doors__card">
      <h2 class="govuk-heading-m govuk-!-margin-bottom-2"><code>{door.name}</code></h2>
      <p class="govuk-body ss-muted">{door.description}</p>
      <a class="govuk-button ss-cta front-doors__open" href={door.href}>
        Open
        <svg width="16" height="16" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <rect x="1" y="1" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" />
          <path d="M5 5 H13 V13" fill="none" stroke="currentColor" stroke-width="1.6" />
        </svg>
      </a>
    </div>
  {/each}
</div>

<style>
  .front-doors {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    margin-top: 30px;
  }

  .front-doors__card {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .front-doors__open {
    margin-top: 15px;
    margin-bottom: 0;
    align-self: flex-start;
  }
</style>
