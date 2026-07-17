<script lang="ts">
  // The paginated 6-wide Pal Box grid (PSP palbox analog). 30 slots per page,
  // circular pager bubbles, keyboard Q/E to navigate (matches PSP). Empty slots
  // padded to PALS_PER_PAGE when not filtering. Client-side search + sort.
  import { t } from '$stores/index';
  import Icon from '@iconify/svelte';
  import PalTile from './PalTile.svelte';
  import type { PalSummary } from '$types/index';

  let {
    pals,
    selectedIds = [],
    playerLevel = 0,
    search = '',
    sort = 'slot',
    onclick,
    onselect,
    onswap,
  }: {
    pals: PalSummary[];
    selectedIds?: string[];
    playerLevel?: number;
    search?: string;
    sort?: 'slot' | 'name' | 'level';
    onclick?: (pal: PalSummary) => void;
    onselect?: (pal: PalSummary) => void;
    onswap?: (sourceId: string, targetId: string) => void;
  } = $props();

  const PALS_PER_PAGE = 30;
  let currentPage = $state(1);

  const filtered = $derived.by(() => {
    let result = [...pals];
    const q = search.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (p) =>
          (p.display_name ?? '').toLowerCase().includes(q) ||
          p.character_id.toLowerCase().includes(q) ||
          (p.nickname ?? '').toLowerCase().includes(q)
      );
    }
    if (sort === 'name') {
      result.sort((a, b) => (a.display_name ?? a.character_id).localeCompare(b.display_name ?? b.character_id));
    } else if (sort === 'level') {
      result.sort((a, b) => (b.level ?? 0) - (a.level ?? 0));
    } else {
      result.sort((a, b) => (a.slot_index ?? 0) - (b.slot_index ?? 0));
    }
    return result;
  });

  const totalPages = $derived(Math.max(1, Math.ceil(filtered.length / PALS_PER_PAGE)));
  // Clamp page when filter shrinks the result set.
  $effect(() => {
    if (currentPage > totalPages) currentPage = totalPages;
  });

  const isFiltering = $derived(search.trim().length > 0);
  const pageItems = $derived.by(() => {
    const start = (currentPage - 1) * PALS_PER_PAGE;
    const slice = filtered.slice(start, start + PALS_PER_PAGE);
    if (isFiltering) return slice; // no padding while filtering
    // Pad to PALS_PER_PAGE with nulls so the grid shape stays stable.
    const out: (PalSummary | null)[] = [...slice];
    while (out.length < PALS_PER_PAGE) out.push(null);
    return out;
  });

  // Pager bubble window (show up to 9 around the current page).
  const visiblePages = $derived.by(() => {
    const pages: number[] = [];
    const start = Math.max(1, currentPage - 4);
    const end = Math.min(totalPages, start + 8);
    for (let p = start; p <= end; p++) pages.push(p);
    return pages;
  });

  function goPage(p: number) {
    currentPage = Math.max(1, Math.min(totalPages, p));
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'q' || e.key === 'Q') { e.preventDefault(); goPage(currentPage - 1); }
    if (e.key === 'e' || e.key === 'E') { e.preventDefault(); goPage(currentPage + 1); }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div>
  <!-- pager -->
  {#if totalPages > 1}
    <div class="flex items-center justify-center gap-2 mb-4">
      <button class="btn text-xs px-2 py-1" disabled={currentPage === 1} onclick={() => goPage(currentPage - 1)} title="Previous (Q)">
        <Icon icon="lucide:chevron-left" width={14} />
      </button>
      <div class="flex gap-1">
        {#each visiblePages as p}
          <button
            class="h-7 w-7 rounded-full text-[11px] font-medium transition-fast {p === currentPage
              ? 'bg-accent text-white shadow-glow-cyan'
              : 'bg-bg-elevated text-ink-secondary hover:bg-bg-hover'}"
            onclick={() => goPage(p)}
            title={`Box ${p}`}
          >{p}</button>
        {/each}
      </div>
      <button class="btn text-xs px-2 py-1" disabled={currentPage === totalPages} onclick={() => goPage(currentPage + 1)} title="Next (E)">
        <Icon icon="lucide:chevron-right" width={14} />
      </button>
    </div>
  {/if}

  <!-- grid -->
  <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 place-items-center p-2">
    {#each pageItems as pal, i (pal?.instance_id ?? `empty-${currentPage}-${i}`)}
      {#if pal}
        <PalTile
          {pal}
          selected={selectedIds.includes(pal.instance_id)}
          {playerLevel}
          {onclick}
          {onselect}
          {onswap}
        />
      {:else}
        <!-- empty slot placeholder (matches tile dimensions) -->
        <div class="h-16 w-16 xl:h-20 xl:w-20 rounded-full border-2 border-dashed border-line/25 bg-bg-deep/30"></div>
      {/if}
    {/each}
  </div>

  {#if filtered.length === 0}
    <p class="text-xs text-ink-dim text-center py-8">{$t('web.pal_editor.palbox_empty')}</p>
  {/if}
</div>
