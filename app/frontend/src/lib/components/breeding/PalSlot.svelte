<script lang="ts">
  // Small reusable pal icon + name pill. Used in chain steps, direct results,
  // and picker selections. Renders an icon (via the shared asset URL helper)
  // plus the display name, with a subtle border/bg treatment.
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import Icon from '@iconify/svelte';

  let {
    tribe,
    display,
    icon,
    size = 'md',
    gender = null,
  }: {
    tribe: string;
    display?: string | null;
    icon?: string | null;
    size?: 'sm' | 'md' | 'lg';
    gender?: string | null;
  } = $props();

  const dims = $derived({ sm: 'w-5 h-5', md: 'w-8 h-8', lg: 'w-12 h-12' }[size]);
  const textSize = $derived({ sm: 'text-[10px]', md: 'text-xs', lg: 'text-sm' }[size]);
  const shown = $derived(display || tribe);
  const genderIcon = $derived(
    gender === 'Male' ? 'lucide:mars' : gender === 'Female' ? 'lucide:venus' : null
  );
  const genderColor = $derived(
    gender === 'Male' ? 'text-sky-400' : gender === 'Female' ? 'text-pink-400' : ''
  );
</script>

<div class="flex items-center gap-1.5 min-w-0">
  <div class="relative shrink-0">
    <img
      src={assetUrl(icon)}
      alt={shown}
      class="{dims} object-contain rounded-2 bg-bg-deep border border-line/40"
      onerror={imgOnError}
      loading="lazy"
    />
    {#if genderIcon}
      <Icon
        icon={genderIcon}
        width={10}
        class="absolute -bottom-0.5 -right-0.5 {genderColor} bg-bg-deep rounded-full p-px"
      />
    {/if}
  </div>
  <div class="min-w-0">
    <p class="{textSize} font-medium text-ink-primary truncate leading-tight">{shown}</p>
    {#if display && display !== tribe}
      <p class="text-[9px] text-ink-dim font-mono truncate leading-tight">{tribe}</p>
    {/if}
  </div>
</div>
