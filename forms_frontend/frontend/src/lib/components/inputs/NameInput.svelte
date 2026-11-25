<script lang="ts">
  interface Props {
    label: string;
    hint?: string | null;
    settings?: Record<string, any>;
    isOptional?: boolean;
    value: string;
    error?: string;
  }

  let { label, hint = null, settings = {}, isOptional = false, value = $bindable(""), error = "" }: Props = $props();

  let title = $state("");
  let firstName = $state("");
  let lastName = $state("");

  const inputType = $derived(settings?.input_type ?? "full_name");
  const titleNeeded = $derived(settings?.title_needed === "true");

  $effect(() => {
    const parts: string[] = [];
    if (titleNeeded && title.trim()) parts.push(title.trim());
    if (firstName.trim()) parts.push(firstName.trim());
    if (lastName.trim()) parts.push(lastName.trim());
    value = parts.join(" ");
  });
</script>

<fieldset class="govuk-fieldset">
  <legend class="govuk-fieldset__legend govuk-fieldset__legend--l">
    <h1 class="govuk-fieldset__heading">
      {label}
      {#if isOptional}
        <span class="govuk-caption-l">(optional)</span>
      {/if}
    </h1>
  </legend>

  {#if hint}
    <div class="govuk-hint">{hint}</div>
  {/if}

  {#if error}
    <p class="govuk-error-message">
      <span class="govuk-visually-hidden">Error:</span> {error}
    </p>
  {/if}

  {#if titleNeeded}
    <div class="govuk-form-group">
      <label class="govuk-label" for="name-title">Title</label>
      <input
        class="govuk-input govuk-input--width-5"
        id="name-title"
        name="name-title"
        type="text"
        autocomplete="honorific-prefix"
        bind:value={title}
      />
    </div>
  {/if}

  {#if inputType === "first_and_last_name" || inputType === "first_middle_and_last_name"}
    <div class="govuk-form-group">
      <label class="govuk-label" for="name-first">First name</label>
      <input
        class="govuk-input"
        class:govuk-input--error={!!error}
        id="name-first"
        name="name-first"
        type="text"
        autocomplete="given-name"
        bind:value={firstName}
      />
    </div>

    <div class="govuk-form-group">
      <label class="govuk-label" for="name-last">Last name</label>
      <input
        class="govuk-input"
        class:govuk-input--error={!!error}
        id="name-last"
        name="name-last"
        type="text"
        autocomplete="family-name"
        bind:value={lastName}
      />
    </div>
  {:else}
    <div class="govuk-form-group">
      <label class="govuk-label" for="name-full">Full name</label>
      <input
        class="govuk-input"
        class:govuk-input--error={!!error}
        id="name-full"
        name="name-full"
        type="text"
        autocomplete="name"
        bind:value={firstName}
      />
    </div>
  {/if}
</fieldset>
