<script lang="ts">
  // Wide horizontal party-slot card (PSP PalCard analog) for the Party column.
  // Richer than the circular tile — shows name, level, gender, badges, and bars
  // inline because the party column only has 5 slots (density matters less).
  import Icon from '@iconify/svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import { draggablePal, dropTargetPal } from '$lib/utils/dragSwap';
  import type { DropTargetOptions } from '$lib/utils/dragSwap';
  import type { PalSummary } from '$types/index';

  let {
    pal,
    selected = false,
    playerLevel = 0,
    onclick,
    onselect,
    onswap,
  }: {
    pal: PalSummary;
    selected?: boolean;
    playerLevel?: number;
    onclick?: (pal: PalSummary) => void;
    onselect?: (pal: PalSummary) => void;
    onswap?: (sourceId: string, targetId: string) => void;
  } = $props();

  const dropOpts = $derived<DropTargetOptions>({
    targetId: pal.instance_id,
    ondrop: (sourceId) => onswap?.(sourceId, pal.instance_id),
  });

  const levelOverPlayer = $derived(
    playerLevel > 0 && (pal.level ?? 0) > playerLevel
  );

  function handleClick(e: MouseEvent) {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      onselect?.(pal);
    } else {
      onclick?.(pal);
    }
  }
</script>

<div
  class="pal-party-card"
  use:draggablePal={pal.instance_id}
  use:dropTargetPal={dropOpts}
>
  <button
    type="button"
    class="w-full text-left rounded-4 border-2 p-2 transition-fast bg-bg-deep/60
      {selected
        ? 'border-accent ring-2 ring-accent/40 shadow-glow-cyan'
        : 'border-line/50 hover:border-accent/50 hover:bg-bg-hover'}
      {pal.is_sick ? 'animate-pulse border-status-error/60' : ''}"
    onclick={handleClick}
    role="button"
    tabindex="0"
    aria-label={pal.display_name ?? pal.character_id}
  >
  <div class="flex items-center gap-2">
    <div class="relative shrink-0">
      <img
        src={assetUrl(pal.icon)}
        alt=""
        class="h-14 w-14 rounded-4 object-cover bg-bg-card border border-line/40"
        onerror={imgOnError}
        loading="lazy"
      />
      {#if pal.is_lucky}
        <span class="absolute -top-1 -left-1 text-yellow-400 text-xs">★</span>
      {:else if pal.is_boss}
        <span class="absolute -top-1 -left-1 text-amber-300 text-[9px] font-bold">α</span>
      {/if}
    </div>
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-ink-muted">Lv</span>
        <span class="text-sm font-bold {levelOverPlayer ? 'text-status-error' : 'text-ink-primary'}">{pal.level ?? 1}</span>
        <Icon
          icon={pal.gender === 'Female' ? 'lucide:venus' : 'lucide:mars'}
          width={12}
          class={pal.gender === 'Female' ? 'text-pink-400' : 'text-sky-400'}
        />
      </div>
      <p class="text-xs font-medium text-ink-primary truncate">{pal.display_name ?? pal.character_id}</p>
      {#if pal.passive_skills.length}
        <div class="flex flex-wrap gap-0.5 mt-0.5">
          {#each pal.passive_skills.slice(0, 3) as skill}
            <span class="text-[8px] px-1 py-0 rounded-2 bg-bg-card text-ink-muted truncate max-w-20">{skill}</span>
          {/each}
          {#if pal.passive_skills.length > 3}
            <span class="text-[8px] text-ink-dim">+{pal.passive_skills.length - 3}</span>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</button>
</div>

<style>
  .pal-party-card:global(.drag-over) > button {
    border-color: #00E5FF !important;
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.4);
  }
</style>
