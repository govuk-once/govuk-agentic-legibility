<script lang="ts">
  import type { Snippet } from 'svelte';
  // Shared (src/lib/schema/kind.ts): the option type
  import type { Choice } from '$lib/schema/kind';
  import Icon from './Icon.svelte';

  interface Props {
    /** Which view of the card to show. */
    view: 'ask' | 'digits' | 'heard' | 'file' | 'working' | 'paused';
    /** The label on the card's tag when someone is asking, for example "Agent is asking". */
    asking: string;
    prompt: string;
    choices?: Choice[] | null;
    /** Option numbers the caller has keyed. */
    highlighted?: number[];
    /** Option numbers the facts suggest. */
    suggested?: number[];
    readout?: string;
    heard?: string;
    hint?: string;
    notice?: string | null;
    /** Why the answer keyed so far can't be sent yet. */
    problem?: string | null;
    error?: string | null;
    /** How many questions the agent has answered so far, shown while it works. */
    answered?: number;
    /** True while answers are keyed. When voice is wired up this is false for spoken answers. */
    byKeys?: boolean;
    startLabel?: string;
    onstart?: () => void;
    children?: Snippet;
  }

  let {
    view,
    asking,
    prompt,
    choices = null,
    highlighted = [],
    suggested = [],
    readout = '',
    heard = '',
    hint = '',
    notice = null,
    problem = null,
    error = null,
    answered = 0,
    byKeys = true,
    startLabel = 'Start answering',
    onstart,
    children
  }: Props = $props();

  // A prompt can run over several lines: the first is the question, the rest read as detail.
  const lines = $derived(prompt.split('\n').filter((line) => line.trim() !== ''));
  const showSuggestion = $derived(highlighted.length === 0);
</script>

<div class="mvi2-card">
  {#if view === 'ask'}
    <span class="mvi2-tag mvi2-tag--agent"><Icon name="wave" width={14} height={12} />{asking}</span>
    {#if choices}
      <h1 class="mvi2-q mvi2-q--lg mvi2-q--left">{lines[0] ?? ''}</h1>
      {#each lines.slice(1) as line, index (index)}
        <p class="mvi2-detail">{line}</p>
      {/each}
      <ul class="mvi2-options">
        {#each choices as choice, index (index)}
          {@const number = index + 1}
          <li class="mvi2-option" class:mvi2-option--picked={showSuggestion && suggested.includes(number)}>
            <span class="mvi2-option__num">{number}</span>
            <span>{choice.label}</span>
          </li>
        {/each}
        {#if choices.length <= 9}
          <li class="mvi2-option">
            <span class="mvi2-option__num">0</span>
            <span>Speak to a person</span>
          </li>
        {/if}
      </ul>
      <div class="mvi2-card__gap"></div>
      <!-- Voice isn't wired up yet, so the microphone is only the look of it. -->
      <div class="mvi2-again">
        <span class="mvi2-again__mic"><Icon name="mic" width={16} height={23} /></span>
        <div>
          <strong>{byKeys ? 'Hold to speak or use keys' : 'Hold to speak'}</strong>
          <span>{byKeys ? 'Press the number of your answer' : 'Say your answer'}</span>
        </div>
      </div>
    {:else}
      <h1 class="mvi2-q">{lines[0] ?? ''}</h1>
      {#each lines.slice(1) as line, index (index)}
        <p class="mvi2-detail">{line}</p>
      {/each}
      <div class="mvi2-card__gap"></div>
      <!-- Voice isn't wired up yet, so the microphone is only the look of it. -->
      <div class="mvi2-mic">
        <div class="mvi2-mic__inner"><Icon name="mic" width={30} height={42} /></div>
      </div>
      <p class="mvi2-big">{byKeys ? 'Hold to speak or use keys' : 'Hold to speak'}</p>
      <p class="mvi2-soft">Let go when you've finished.</p>
      <div class="mvi2-card__gap"></div>
    {/if}
  {:else if view === 'digits'}
    <span class="mvi2-tag"><span class="mvi2-tag__dot"></span>Your turn · keypad</span>
    <h1 class="mvi2-q">{lines[0] ?? ''}</h1>
    <div class="mvi2-card__gap"></div>
    <p class="mvi2-readout">
      {#each readout.split(' ') as part, index (index)}
        <span>{part}</span>
      {/each}
    </p>
    <div class="mvi2-underline"></div>
    {#if hint}
      <p class="mvi2-soft">{hint}</p>
    {/if}
    <div class="mvi2-card__gap"></div>
  {:else if view === 'heard'}
    <span class="mvi2-tag"><span class="mvi2-tag__dot"></span>Check your answer</span>
    <h1 class="mvi2-q mvi2-q--left">{lines[0] ?? ''}</h1>
    <p class="mvi2-heard-label">{byKeys ? 'The service received' : 'The service heard'}</p>
    <div class="mvi2-heard">
      <Icon name={byKeys ? 'keys' : 'wave'} />
      <span>“{heard}”</span>
    </div>
    <div class="mvi2-card__gap"></div>
    <div class="mvi2-again">
      <span class="mvi2-again__mic"><Icon name="mic" width={16} height={23} /></span>
      <div>
        <strong>{byKeys ? 'Hold to speak instead' : 'Hold to speak again'}</strong>
        <span>Press ✓ if that's right</span>
      </div>
    </div>
  {:else if view === 'file'}
    <span class="mvi2-tag mvi2-tag--agent"><Icon name="wave" width={14} height={12} />{asking}</span>
    <h1 class="mvi2-q mvi2-q--left">{lines[0] ?? ''}</h1>
    <div class="mvi2-card__gap"></div>
    {#if children}
      <div class="mvi2-note">{@render children()}</div>
    {/if}
    <div class="mvi2-card__gap"></div>
  {:else if view === 'working'}
    <span class="mvi2-tag mvi2-tag--agent"><Icon name="wave" width={14} height={12} />Agent is working</span>
    <div class="mvi2-card__gap"></div>
    <div class="mvi2-orb"><Icon name="logo-moving" width={120} height={73} /></div>
    <p class="mvi2-big">Working through your details</p>
    <p class="mvi2-soft">
      {answered === 0 ? 'Reading what you told me.' : `Answered ${answered} from your facts so far.`}
    </p>
    <div class="mvi2-card__gap"></div>
  {:else}
    <span class="mvi2-tag mvi2-tag--agent"><Icon name="wave" width={14} height={12} />Agent is ready</span>
    <div class="mvi2-card__gap"></div>
    <div class="mvi2-orb"><Icon name="logo" width={120} height={73} /></div>
    <p class="mvi2-big">Ready when you are</p>
    <p class="mvi2-soft">I'll answer what I can from your facts and ask you the rest.</p>
    {#if onstart}
      <button type="button" class="mvi2-btn mvi2-btn--card" onclick={onstart}>{startLabel}</button>
    {/if}
    <div class="mvi2-card__gap"></div>
  {/if}

  {#if problem && (view === 'heard' || view === 'digits')}
    <p class="mvi2-error">{problem}</p>
  {/if}
  {#if notice}
    <p class="mvi2-note">{notice}</p>
  {/if}
  {#if error}
    <p class="mvi2-error">{error}</p>
  {/if}
</div>
