<script lang="ts">
  interface Props {
    name: string;
    value: string;
    group: string;
    label: string;
    hint?: string;
    size?: 'normal' | 'small' | 'compact';
    disabled?: boolean;
  }

  let { name, value, group = $bindable(), label, hint, size = 'normal', disabled = false }: Props = $props();
</script>

<label
  class="mvi2-radio"
  class:mvi2-radio--small={size === 'small'}
  class:mvi2-radio--compact={size === 'compact'}
>
  <input class="mvi2-sr mvi2-radio__input" type="radio" {name} {value} {disabled} bind:group />
  <span class="mvi2-radio__mark"></span>
  <span class="mvi2-radio__text">
    <span class="mvi2-radio__label">{label}</span>
    {#if hint}
      <span class="mvi2-radio__hint">{hint}</span>
    {/if}
  </span>
</label>
