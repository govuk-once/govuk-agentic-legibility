<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    name: string;
    value: string;
    group: string;
    /** Journey name, for example "Change of address". */
    label: string;
    /** Department the journey belongs to, for example "DVLA". */
    department: string;
    icon: 'home' | 'home-plus' | 'heart' | 'passport';
    /** Roughly how long it takes. A placeholder until the journeys say so themselves. */
    minutes: number;
    /** Background of the icon tile, picked per card. */
    tile: string;
    /** For a card that only holds the place of a journey that doesn't exist yet. */
    disabled?: boolean;
  }

  let { name, value, group = $bindable(), label, department, icon, minutes, tile, disabled = false }: Props = $props();
</script>

<label class="mvi2-service">
  <input class="mvi2-sr" type="radio" {name} {value} {disabled} bind:group />
  <span class="mvi2-service__tile" style:background-color={tile}>
    <Icon name={icon} />
    <span class="mvi2-service__tick"><Icon name="tick" width={11} height={9} /></span>
  </span>
  <span class="mvi2-service__dept">{department}</span>
  <span class="mvi2-service__name">{label}</span>
  <span class="mvi2-service__time"><Icon name="clock" />{minutes} min</span>
</label>
