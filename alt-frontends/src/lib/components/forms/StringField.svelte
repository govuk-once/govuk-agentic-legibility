<script lang="ts">
  import type { SchemaDefinition } from '$lib/types';

  interface Props {
    schema: SchemaDefinition;
    value: string;
  }

  let { schema, value = $bindable('') }: Props = $props();
</script>

<input
  class="govuk-input"
  type="text"
  maxlength={schema.max_length ?? undefined}
  bind:value
/>
