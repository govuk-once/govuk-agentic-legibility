<script lang="ts">
  import type { SchemaDefinition } from '$lib/types';

  interface Props {
    schema: SchemaDefinition;
    value: { ref: string; bytes: number } | null;
  }

  let { schema, value = $bindable(null) }: Props = $props();

  // No upload backend exists yet (no /uploads route in agent/api/), so this
  // satisfies interpreter.py's file_ref validator (a non-empty `ref` and
  // `bytes > 0`) using the picked file's own name/size as a stand-in.
  function onchange(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    value = file ? { ref: file.name, bytes: file.size } : null;
  }
</script>

<input class="govuk-file-upload" type="file" accept={schema.accept?.join(',')} {onchange} />
