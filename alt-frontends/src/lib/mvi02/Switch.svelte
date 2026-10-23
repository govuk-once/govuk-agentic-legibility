<script lang="ts">
  interface Props {
    checked: boolean;
    label: string;
    disabled?: boolean;
    /** Called with the new value after a press, for switches that aren't bound to a variable. */
    onchange?: (checked: boolean) => void;
  }

  let { checked = $bindable(), label, disabled = false, onchange }: Props = $props();

  function toggle() {
    const next = !checked;
    checked = next;
    onchange?.(next);
  }
</script>

<button
  type="button"
  role="switch"
  class="mvi2-switch"
  aria-checked={checked}
  aria-label={label}
  {disabled}
  onclick={toggle}
></button>
