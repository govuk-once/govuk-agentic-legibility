<script lang="ts">
  // The small icons the /mvi02 design uses. Drawn inline so they take no extra requests.
  type IconName =
    | 'logo'
    | 'logo-moving'
    | 'keys'
    | 'home'
    | 'home-plus'
    | 'heart'
    | 'passport'
    | 'clock'
    | 'wave'
    | 'mic'
    | 'backspace'
    | 'tick'
    | 'arrow'
    | 'chevron'
    | 'person'
    | 'send'
    | 'check-circle'
    | 'circle'
    | 'close';

  interface Props {
    name: IconName;
    width?: number;
    height?: number;
    /** Stroke or fill colour for icons that take one. */
    color?: string;
  }

  let { name, width, height, color = 'currentColor' }: Props = $props();
</script>

{#if name === 'logo'}
  <svg width={width ?? 21} height={height ?? 13} viewBox="78 141 1032 620" aria-hidden="true" focusable="false">
    <circle cx="388" cy="451" r="310" fill="#BC52FF" />
    <circle cx="800" cy="451" r="310" fill="#12E2F7" />
    <path d="M594 219.3A310 310 0 0 1 594 682.7A310 310 0 0 1 594 219.3Z" fill="#C0EAFD" />
  </svg>
{:else if name === 'logo-moving'}
  <!-- The logo with its two circles drifting together and apart. The lens is the overlap, so it
       is the first circle clipped by the second, and both move the same way. -->
  <svg width={width ?? 21} height={height ?? 13} viewBox="78 141 1032 620" aria-hidden="true" focusable="false">
    <defs>
      <clipPath id="mvi2-lens-clip">
        <circle class="mvi2-dot mvi2-dot--b" cx="800" cy="451" r="310" />
      </clipPath>
    </defs>
    <circle class="mvi2-dot mvi2-dot--a" cx="388" cy="451" r="310" fill="#BC52FF" />
    <circle class="mvi2-dot mvi2-dot--b" cx="800" cy="451" r="310" fill="#12E2F7" />
    <circle class="mvi2-dot mvi2-dot--a" cx="388" cy="451" r="310" fill="#C0EAFD" clip-path="url(#mvi2-lens-clip)" />
  </svg>
{:else if name === 'keys'}
  <svg width={width ?? 22} height={height ?? 22} viewBox="0 0 22 22" aria-hidden="true" focusable="false">
    <g fill={color === 'currentColor' ? '#02064A' : color}>
      <circle cx="4" cy="4" r="2.2" /><circle cx="11" cy="4" r="2.2" /><circle cx="18" cy="4" r="2.2" />
      <circle cx="4" cy="11" r="2.2" /><circle cx="11" cy="11" r="2.2" /><circle cx="18" cy="11" r="2.2" />
      <circle cx="4" cy="18" r="2.2" /><circle cx="11" cy="18" r="2.2" /><circle cx="18" cy="18" r="2.2" />
    </g>
  </svg>
{:else if name === 'home' || name === 'home-plus'}
  <svg width={width ?? 30} height={height ?? 27} viewBox="0 0 44 40" aria-hidden="true" focusable="false">
    <g fill="none" stroke="#02064A" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 19L22 4L40 19" />
      <path d="M9 16V36H35V16" />
      {#if name === 'home'}
        <path d="M18 36V26H26V36" />
      {:else}
        <path d="M16 26H28M22 20V32" />
      {/if}
    </g>
  </svg>
{:else if name === 'heart'}
  <svg width={width ?? 28} height={height ?? 28} viewBox="0 0 40 40" aria-hidden="true" focusable="false">
    <path d="M20 35C8 26 4 19 4 13.5C4 9 7.5 6 11.5 6C15 6 18 8 20 11C22 8 25 6 28.5 6C32.5 6 36 9 36 13.5C36 19 32 26 20 35Z" fill="none" stroke="#02064A" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'passport'}
  <svg width={width ?? 26} height={height ?? 30} viewBox="0 0 26 30" aria-hidden="true" focusable="false">
    <rect x="3" y="2" width="20" height="26" rx="3" fill="none" stroke="#02064A" stroke-width="3" />
    <circle cx="13" cy="12" r="4" fill="none" stroke="#02064A" stroke-width="2.6" />
    <path d="M8 21H18" fill="none" stroke="#02064A" stroke-width="2.6" stroke-linecap="round" />
  </svg>
{:else if name === 'clock'}
  <svg width={width ?? 14} height={height ?? 14} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    <circle cx="8" cy="8" r="6.5" fill="none" stroke="#484949" stroke-width="1.6" />
    <path d="M8 4.5V8L10.5 9.5" fill="none" stroke="#484949" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'wave'}
  <svg width={width ?? 28} height={height ?? 24} viewBox="0 0 20 16" aria-hidden="true" focusable="false">
    <path
      d="M2 6v4M6 3.5v9M10 1v14M14 3.5v9M18 6v4"
      fill="none"
      stroke={color === 'currentColor' ? '#02064A' : color}
      stroke-width="1.8"
      stroke-linecap="round"
    />
  </svg>
{:else if name === 'mic'}
  <svg width={width ?? 34} height={height ?? 48} viewBox="0 0 34 48" aria-hidden="true" focusable="false">
    <rect x="11" y="2" width="12" height="24" rx="6" fill="#12E2F7" />
    <path d="M4 20C4 29 10 33 17 33C24 33 30 29 30 20" fill="none" stroke="#FFFFFF" stroke-width="2.8" stroke-linecap="round" />
    <path d="M17 33V42M10 42H24" fill="none" stroke="#FFFFFF" stroke-width="2.8" stroke-linecap="round" />
  </svg>
{:else if name === 'backspace'}
  <svg width={width ?? 26} height={height ?? 20} viewBox="0 0 24 17" aria-hidden="true" focusable="false">
    <path d="M8 1H22V16H8L1 8.5Z" fill="none" stroke="#0B0C0C" stroke-width="1.6" stroke-linejoin="round" />
    <path d="M12 5.5L18 11.5M18 5.5L12 11.5" fill="none" stroke="#0B0C0C" stroke-width="1.6" stroke-linecap="round" />
  </svg>
{:else if name === 'tick'}
  <svg width={width ?? 26} height={height ?? 20} viewBox="0 0 22 17" aria-hidden="true" focusable="false">
    <path d="M2 9L8 15L20 2" fill="none" stroke="#12E2F7" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'arrow'}
  <svg width={width ?? 18} height={height ?? 14} viewBox="0 0 18 14" aria-hidden="true" focusable="false">
    <path d="M1 7H16M10 1.5L16 7L10 12.5" fill="none" stroke={color} stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'chevron'}
  <svg width={width ?? 7} height={height ?? 12} viewBox="0 0 9 15" aria-hidden="true" focusable="false">
    <path d="M1.5 1.5L7 7.5L1.5 13.5" fill="none" stroke={color} stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'person'}
  <svg width={width ?? 20} height={height ?? 20} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
    <circle cx="10" cy="7" r="3.4" fill="#02064A" />
    <path d="M3.5 17.2a6.5 6.5 0 0 1 13 0" fill="none" stroke="#02064A" stroke-width="2.4" stroke-linecap="round" />
  </svg>
{:else if name === 'send'}
  <svg width={width ?? 15} height={height ?? 17} viewBox="0 0 15 17" aria-hidden="true" focusable="false">
    <path d="M7.5 16V2M1.5 8L7.5 1.6L13.5 8" fill="none" stroke="#12E2F7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'check-circle'}
  <svg width={width ?? 28} height={height ?? 28} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
    <circle cx="14" cy="14" r="13" fill="#0F7A52" />
    <path d="M8 14.4L12.3 18.5L20 10.5" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
{:else if name === 'circle'}
  <svg width={width ?? 28} height={height ?? 28} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
    <circle cx="14" cy="14" r="12.6" fill="none" stroke="#B1B4B6" stroke-width="2" />
  </svg>
{:else if name === 'close'}
  <svg width={width ?? 14} height={height ?? 14} viewBox="0 0 14 14" aria-hidden="true" focusable="false">
    <path d="M1.5 1.5L12.5 12.5M12.5 1.5L1.5 12.5" fill="none" stroke="#0B0C0C" stroke-width="2.2" stroke-linecap="round" />
  </svg>
{/if}
