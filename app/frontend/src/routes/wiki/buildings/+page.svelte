<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface Building {
    name: string; asset: string; icon: string; description?: string;
    type_a_display?: string; rank?: number; hp?: number; defense?: number;
    required_work_amount?: number; deterioration_damage?: number;
    materials?: { id: string; count: number }[];
    belongs_to_base?: boolean;
  }

  let buildings = $state<Building[]>([]);
  let loading = $state(true);
  let search = $state('');
  let typeFilter = $state('All');
  let selected = $state<Building | null>(null);

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/world');
      const json = await res.json();
      buildings = (json.data.structures as Building[]).filter((b: Building) => b.name);
    } catch (e) { console.error('Buildings wiki load failed:', e); }
    finally { loading = false; }
  });

  const types = $derived.by(() => {
    const set = new Set<string>();
    for (const b of buildings) if (b.type_a_display) set.add(b.type_a_display);
    return ['All', ...set];
  });

  const filtered = $derived.by(() => {
    let result = buildings;
    if (typeFilter !== 'All') result = result.filter((b) => b.type_a_display === typeFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((b) => b.name.toLowerCase().includes(q) || b.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => a.name.localeCompare(b.name));
  });
</script>

<div class="flex h-full gap-4">
  <div class="w-64 shrink-0 flex flex-col bg-bg-deep/25 rounded-4 p-2">
    <div class="flex items-center justify-between mb-2 px-1">
      <span class="text-[11px] text-ink-dim font-semibold tracking-wide uppercase">{$t('web.wiki.entries_count', { count: filtered.length })}</span>
    </div>
    <div class="relative mb-3 px-1">
      <Icon icon="lucide:search" width={14} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder={$t('web.wiki.search_buildings')} class="input pl-8 text-xs" />
    </div>
    <div class="flex flex-wrap gap-1 mb-3 px-1">
      {#each types as t}
        <button class="chip text-[10px] px-2 py-0.5 cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {typeFilter === t ? 'chip-blue' : ''}" onclick={() => (typeFilter = t)}>{t}</button>
      {/each}
    </div>
    <div class="flex-1 overflow-y-auto space-y-0.5">
      {#each filtered as b}
        <button
          class="flex w-full items-center gap-2 px-2.5 py-1.5 rounded-4 text-left text-xs transition-all {selected?.asset === b.asset ? 'bg-accent/15 border-2 border-accent/30' : 'hover:bg-bg-hover border-2 border-transparent'}"
          onclick={() => (selected = b)}
        >
          <img src={assetUrl(b.icon)} alt={b.name} class="w-6 h-6 shrink-0 object-contain" onerror={imgOnError} loading="lazy" />
          <span class="font-medium text-ink-primary truncate flex-1">{b.name}</span>
          {#if b.rank}
            <span class="chip text-[10px] ml-auto shrink-0">{$t('web.wiki.tier_n', { rank: b.rank })}</span>
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
          <img src={assetUrl(selected.icon)} alt={selected.name} class="w-12 h-12 object-contain shrink-0 bg-bg-deep rounded-4 border-2 border-line/30 p-1" onerror={imgOnError} />
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-lg font-bold text-ink-emphasis">{selected.name}</h2>
              {#if selected.rank}
                <span class="chip chip-amber text-[10px]">{$t('web.wiki.tier_n', { rank: selected.rank })}</span>
              {/if}
            </div>
            <span class="text-[11px] text-ink-dim font-mono">{selected.asset}</span>
            <span class="chip text-[10px] ml-2">{selected.type_a_display ?? ''}</span>
          </div>
        </div>

        <p class="text-xs text-ink-secondary leading-relaxed">{selected.description ?? ''}</p>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">{$t('web.wiki.stat_hp')}</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.hp ?? 0}</p>
          </div>
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">{$t('web.wiki.stat_defense')}</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.defense ?? 0}</p>
          </div>
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">{$t('web.wiki.stat_work_amount')}</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.required_work_amount ?? 0}</p>
          </div>
          <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
            <p class="text-[10px] text-ink-dim uppercase">{$t('web.wiki.stat_deterioration')}</p>
            <p class="text-sm font-bold text-ink-emphasis">{selected.deterioration_damage ?? 0}</p>
          </div>
        </div>

        {#if selected.materials?.length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.wiki.materials')}</h3>
            <div class="flex flex-wrap gap-1.5">
              {#each selected.materials as mat}
                <span class="chip text-[10px]">{mat.id} <span class="font-bold text-accent-light">x{mat.count}</span></span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-ink-dim gap-2">
        <Icon icon="lucide:building-2" width={32} class="text-ink-muted" />
        <p class="text-xs">{$t('web.wiki.select_building')}</p>
      </div>
    {/if}
  </div>
</div>
