<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface Tech {
    name: string; asset: string; icon: string; description: string;
    type: string; level_cap: number; tier: number; cost: number;
    require_technology: string[]; is_boss_tech: boolean;
    unlock_build_objects: string[]; unlock_item_recipes: string[];
  }

  let techs = $state<Tech[]>([]);
  let loading = $state(true);
  let search = $state('');
  let selected = $state<Tech | null>(null);
  let bossFilter = $state('All');
  let sortKey = $state<'name' | 'tier' | 'level_cap' | 'cost'>('tier');
  let sortAsc = $state(true);

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/world');
      const json = await res.json();
      techs = (json.data.technology as Tech[]).filter((t: Tech) => t.name);
    } catch { /* ignore */ }
    finally { loading = false; }
  });

  const filtered = $derived.by(() => {
    let result = techs;
    if (bossFilter === 'boss') result = result.filter((t) => t.is_boss_tech);
    else if (bossFilter === 'normal') result = result.filter((t) => !t.is_boss_tech);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((t) => t.name.toLowerCase().includes(q) || t.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'tier') cmp = (a.tier ?? 0) - (b.tier ?? 0);
      else if (sortKey === 'level_cap') cmp = (a.level_cap ?? 0) - (b.level_cap ?? 0);
      else if (sortKey === 'cost') cmp = (a.cost ?? 0) - (b.cost ?? 0);
      return sortAsc ? cmp : -cmp;
    });
  });

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }
</script>

<div class="flex h-full gap-4">
  <div class="w-64 shrink-0 flex flex-col bg-bg-deep/25 rounded-4 p-2">
    <div class="flex items-center justify-between mb-2 px-1">
      <span class="text-[11px] text-ink-dim font-semibold tracking-wide uppercase">{filtered.length} entries</span>
    </div>
    <div class="relative mb-3 px-1">
      <Icon icon="lucide:search" width={14} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder="Search technologies..." class="input pl-8 text-xs" />
    </div>
    <div class="flex gap-1 mb-3 px-1">
      <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {bossFilter === 'All' ? 'chip-blue' : ''}" onclick={() => (bossFilter = 'All')}>All</button>
      <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {bossFilter === 'normal' ? 'chip-blue' : ''}" onclick={() => (bossFilter = 'normal')}>Normal</button>
      <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {bossFilter === 'boss' ? 'chip-blue' : ''}" onclick={() => (bossFilter = 'boss')}>Boss</button>
    </div>
    <div class="flex-1 overflow-y-auto space-y-0.5">
      {#each filtered as tech}
        <button
          class="flex w-full items-center gap-2 px-2.5 py-1.5 rounded-4 text-left text-xs transition-all {selected?.asset === tech.asset ? 'bg-accent/15 border-2 border-accent/30' : 'hover:bg-bg-hover border-2 border-transparent'}"
          onclick={() => (selected = tech)}
        >
          <img src={assetUrl(tech.icon)} alt={tech.name} class="w-6 h-6 shrink-0 object-contain" onerror={imgOnError} loading="lazy" />
          <span class="font-medium text-ink-primary truncate flex-1">{tech.name}</span>
          {#if tech.tier}
            <span class="chip text-[10px] ml-auto shrink-0">Tier {tech.tier}</span>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="flex items-center justify-center h-full"><Spinner /></div>
    {:else if selected}
      <div class="card space-y-4">
        <div class="flex items-center gap-3">
          <img src={assetUrl(selected.icon)} alt={selected.name} class="w-10 h-10 object-contain shrink-0" onerror={imgOnError} />
          <div>
            <h2 class="text-lg font-bold text-ink-emphasis">{selected.name}</h2>
            <div class="flex items-center gap-1 mt-1">
              <span class="chip chip-amber text-[10px]">Tier {selected.tier}</span>
              <span class="chip text-[10px]">{selected.type}</span>
              <span class="chip {selected.is_boss_tech ? 'chip-purple' : 'chip-green'} text-[10px]">{selected.is_boss_tech ? 'Boss' : 'Normal'}</span>
            </div>
            <span class="text-[11px] text-ink-dim font-mono block mt-1">{selected.asset}</span>
          </div>
        </div>

        <p class="text-xs text-ink-secondary leading-relaxed">{selected.description}</p>

        <div class="grid grid-cols-3 gap-2">
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">Level</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.level_cap}</p>
          </div>
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">Tech Points</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.cost}</p>
          </div>
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">Prerequisites</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.require_technology?.length ?? 0}</p>
          </div>
        </div>

        {#if selected.require_technology?.length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Prerequisites</h3>
            <div class="flex flex-wrap gap-1">
              {#each selected.require_technology as req}
                <span class="chip text-[10px]">{req}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if selected.unlock_build_objects?.length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Unlocks Buildings</h3>
            <div class="flex flex-wrap gap-1">
              {#each selected.unlock_build_objects as obj}
                <span class="chip chip-blue text-[10px]">{obj}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if selected.unlock_item_recipes?.length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Unlocks Items</h3>
            <div class="flex flex-wrap gap-1">
              {#each selected.unlock_item_recipes as item}
                <span class="chip chip-green text-[10px]">{item}</span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-ink-dim gap-2">
        <Icon icon="lucide:microscope" width={32} class="text-ink-muted" />
        <p class="text-xs">Select a technology to view details</p>
      </div>
    {/if}
  </div>
</div>
