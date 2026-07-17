<script lang="ts">
  // Circular pal slot tile — the dense grid cell (PSP PalBadge analog).
  // Shows icon + gender corner + special badge + level; selection + sick states.
  // Click opens the detail modal; Ctrl/Cmd-click toggles multi-select.
  // Keeps the tile minimal (PSP convention) — IVs/souls/skills live in the
  // hover popup (PalTilePopup) to preserve grid density.
  import Icon from '@iconify/svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import { draggablePal, dropTargetPal } from '$lib/utils/dragSwap';
  import PalTilePopup from './PalTilePopup.svelte';
  import type { PalSummary } from '$types/index';
  import type { DropTargetOptions } from '$lib/utils/dragSwap';

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

  let hover = $state(false);

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
  class="relative pal-tile"
  use:draggablePal={pal.instance_id}
  use:dropTargetPal={dropOpts}
>
  <button
    type="button"
    class="relative h-16 w-16 xl:h-20 xl:w-20 rounded-full outline outline-2 outline-offset-2 transition-fast
      {selected
        ? 'outline-accent ring-4 ring-accent/60 shadow-glow-cyan'
        : 'outline-line/50 hover:outline-accent/60 hover:ring-4 hover:ring-accent/30'}
      {pal.is_sick ? 'animate-pulse ring-4 ring-status-error' : ''}"
    onclick={handleClick}
    onmouseenter={() => (hover = true)}
    onmouseleave={() => (hover = false)}
    role="button"
    tabindex="0"
    aria-label={pal.display_name ?? pal.character_id}
  >
    <img
      src={assetUrl(pal.icon)}
      alt={pal.display_name ?? pal.character_id}
      class="h-16 w-16 xl:h-20 xl:w-20 rounded-full object-cover bg-bg-deep"
      onerror={imgOnError}
      loading="lazy"
    />

    <!-- gender: top-right -->
    <span
      class="absolute -top-1 -right-1 xl:-right-2 flex h-5 w-5 xl:h-6 xl:w-6 items-center justify-center rounded-full bg-bg-deep border border-line/60
        {pal.gender === 'Female' ? 'text-pink-400' : 'text-sky-400'}"
    >
      <Icon icon={pal.gender === 'Female' ? 'lucide:venus' : 'lucide:mars'} width={12} />
    </span>

    <!-- special badge: top-left (one at a time — boss/lucky/predator) -->
    {#if pal.is_lucky}
      <span class="absolute -top-1 -left-1 xl:-left-2 flex h-5 w-5 xl:h-6 xl:w-6 items-center justify-center rounded-full bg-yellow-500/20 border border-yellow-500/60 text-yellow-400 text-xs font-bold">★</span>
    {:else if pal.is_boss}
      <span class="absolute -top-1 -left-1 xl:-left-2 flex h-5 w-5 xl:h-6 xl:w-6 items-center justify-center rounded-full bg-amber-600/30 border border-amber-500/60 text-amber-300 text-[8px] font-bold">α</span>
    {:else if pal.is_predator}
      <span class="absolute -top-1 -left-1 xl:-left-2 flex h-5 w-5 xl:h-6 xl:w-6 items-center justify-center rounded-full bg-rose-600/30 border border-rose-500/60 text-rose-300 text-[8px] font-bold">P</span>
    {/if}

    <!-- level: bottom-left -->
    {#if pal.level}
      <span class="absolute -bottom-2 left-0 xl:-left-1 text-[10px] font-bold {levelOverPlayer ? 'text-status-error' : 'text-ink-primary'} bg-bg-deep/90 px-1 rounded-2">
        {pal.level}
      </span>
    {/if}

    <!-- element badges: bottom-right stack (at-a-glance, on the tile) -->
    {#if pal.elements && Object.keys(pal.elements).length > 0}
      <span class="absolute -bottom-1 right-0 xl:-right-1 flex flex-col gap-px items-end">
        {#each Object.values(pal.elements).slice(0, 2) as el}
          <img
            src={assetUrl(el.icon)}
            alt={el.name}
            title={el.name}
            class="w-3.5 h-3.5 rounded-full bg-bg-deep/90 border border-line/40 object-contain p-px"
            onerror={imgOnError}
            loading="lazy"
          />
        {/each}
      </span>
    {/if}

    <!-- passive markers: 4 pips along the top edge (at-a-glance).
         Filled = a passive occupies that slot; color-coded by rank tier so a
         "good" passive set reads as brighter pips. Empty = no passive there. -->
    {#if pal.passive_skills.length > 0}
      <span class="absolute top-0.5 left-1/2 -translate-x-1/2 flex gap-px">
        {#each Array(4) as _, i}
          <span
            class="w-1 h-1 rounded-full {i < pal.passive_skills.length
              ? (i === 0 ? 'bg-emerald-400' : i === 1 ? 'bg-sky-400' : i === 2 ? 'bg-accent' : 'bg-amber-400')
              : 'bg-line/40'}"
          ></span>
        {/each}
      </span>
    {/if}
  </button>

  {#if hover}
    <div class="absolute z-50 left-full top-0 ml-2 hidden xl:block">
      <PalTilePopup {pal} />
    </div>
  {/if}
</div>

<style>
  /* Drop-target highlight: a neon ring + scale when a pal is dragged over.
     Toggled via the `drag-over` class by the dropTargetPal action. */
  .pal-tile:global(.drag-over) {
    transform: scale(1.08);
    transition: transform 0.1s ease-out;
  }
  .pal-tile:global(.drag-over) > button {
    outline-color: #00E5FF !important;
    box-shadow: 0 0 16px rgba(0, 229, 255, 0.5);
  }
</style>
