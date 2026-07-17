<script lang="ts">
  // Reusable searchable skill selector. Renders the currently-selected skills
  // as removable chips, plus a searchable dropdown to add more. Used for both
  // passives (bare asset IDs) and active waza (EPalWazaID::-prefixed).
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import { clickOutside } from '$lib/utils/clickOutside';
  import Icon from '@iconify/svelte';
  import type { SkillCatalogEntry } from '$types/index';

  let {
    catalog,
    selected,
    slotCap = 99,
    prefix = '',
    onselect,
    onremove,
  }: {
    catalog: SkillCatalogEntry[];
    selected: string[];
    slotCap?: number;
    prefix?: string;
    onselect: (asset: string) => void;
    onremove: (asset: string) => void;
  } = $props();

  let open = $state(false);
  let query = $state('');

  // Normalize selected IDs: strip the prefix for display matching.
  const bare = (s: string) => (prefix && s.startsWith(prefix) ? s.slice(prefix.length) : s);
  const selectedBare = $derived(selected.map(bare));

  const filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    const sel = new Set(selectedBare.map((s) => s.toLowerCase()));
    let result = catalog.filter((e) => !sel.has(String(e.asset).toLowerCase()));
    if (q) {
      result = result.filter(
        (e) =>
          String(e.asset).toLowerCase().includes(q) ||
          String(e.name ?? '').toLowerCase().includes(q)
      );
    }
    return result.slice(0, 80); // cap dropdown render size
  });

  const atCap = $derived(selected.length >= slotCap);
  const lookup = $derived(new Map(catalog.map((e) => [String(e.asset).toLowerCase(), e])));

  function displayFor(assetBare: string): string {
    return lookup.get(assetBare.toLowerCase())?.name ?? assetBare;
  }

  function pick(entry: SkillCatalogEntry) {
    open = false;
    query = '';
    onselect(entry.asset);
  }
</script>

<div class="space-y-2">
  {#if selectedBare.length}
    <div class="flex flex-wrap gap-1.5">
      {#each selectedBare as asset}
        <span class="chip text-[11px] px-2 py-0.5 chip-green flex items-center gap-1">
          {displayFor(asset)}
          <button class="text-ink-dim hover:text-rose-400 transition-fast" onclick={() => onremove(asset)} title="Remove">
            <Icon icon="lucide:x" width={10} />
          </button>
        </span>
      {/each}
    </div>
  {/if}

  {#if !atCap}
    <div class="relative" use:clickOutside={() => (open = false)}>
      <button
        type="button"
        class="input flex items-center gap-2 text-left cursor-pointer hover:border-accent/50 transition-fast text-xs"
        onclick={() => (open = !open)}
      >
        <Icon icon="lucide:plus" width={12} class="text-ink-dim" />
        <span class="text-ink-dim flex-1">{query || 'Add skill…'}</span>
        <Icon icon="lucide:chevron-down" width={12} class="text-ink-dim" />
      </button>
      {#if open}
        <div class="absolute z-50 mt-1 w-full bg-bg-card border border-line/60 rounded-4 shadow-xl flex flex-col max-h-72">
          <div class="p-2 border-b border-line/40">
            <input type="text" bind:value={query} placeholder="Search…" class="input text-xs" autocomplete="off" />
          </div>
          <div class="overflow-y-auto flex-1">
            {#if filtered.length === 0}
              <p class="text-xs text-ink-dim p-3 text-center">No matches</p>
            {:else}
              {#each filtered as entry (entry.asset)}
                <button
                  type="button"
                  class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-bg-hover transition-fast"
                  onclick={() => pick(entry)}
                >
                  {#if entry.icon}
                    <img src={assetUrl(entry.icon)} alt="" class="w-4 h-4 object-contain" onerror={imgOnError} loading="lazy" />
                  {/if}
                  <span class="font-medium text-ink-primary truncate flex-1">{entry.name}</span>
                  <span class="text-[9px] text-ink-dim font-mono shrink-0">{entry.asset}</span>
                </button>
              {/each}
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <p class="text-[10px] text-ink-dim italic">Slot limit reached ({slotCap}).</p>
  {/if}
</div>
