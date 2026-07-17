<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';

  interface Passive {
    name: string; asset: string; rank: number; description: string;
    icon: string;
    effect1: number; effect2: number; effect3: number; effect4: number;
    efftype1: string; efftype2: string; efftype3: string; efftype4: string;
    category: string;
  }

  let passives = $state<Passive[]>([]);
  let loading = $state(true);
  let search = $state('');
  let rankFilter = $state(0);
  let sortKey = $state<'name' | 'rank'>('name');
  let sortAsc = $state(true);

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/skills');
      const json = await res.json();
      passives = (json.data.passives as Passive[]).filter((p: Passive) => p.name && p.category !== 'EPalPassiveCategory::SortNotDisplayable');
    } catch { /* ignore */ }
    finally { loading = false; }
  });

  const filtered = $derived.by(() => {
    let result = passives;
    if (rankFilter > 0) result = result.filter((p) => p.rank === rankFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q) || p.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'rank') cmp = a.rank - b.rank;
      return sortAsc ? cmp : -cmp;
    });
  });

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }

  function renderEffects(p: Passive): string[] {
    const out: string[] = [];
    const pairs = [
      [p.efftype1, p.effect1] as const,
      [p.efftype2, p.effect2] as const,
      [p.efftype3, p.effect3] as const,
      [p.efftype4, p.effect4] as const,
    ];
    for (const [type, val] of pairs) {
      if (type && !type.startsWith('EPalPassiveSkillEffectType::no') && val !== 0) {
        const label = type.replace('EPalPassiveSkillEffectType::', '');
        out.push(`${label} ${val > 0 ? '+' : ''}${val}%`);
      }
    }
    return out;
  }
</script>

<div class="flex flex-col h-full gap-3">
  <div class="flex items-center gap-3 flex-wrap">
    <div class="relative flex-1 max-w-xs">
      <Icon icon="lucide:search" width={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder={$t('web.wiki.search_passive')} class="input pl-8 text-xs" />
    </div>
    <div class="flex gap-1 flex-wrap items-center">
      <span class="text-[10px] text-ink-dim font-semibold uppercase tracking-wider mr-1">{$t('web.wiki.filter_rank')}</span>
      <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {rankFilter === 0 ? 'chip-blue' : ''}" onclick={() => (rankFilter = 0)}>{$t('web.wiki.all')}</button>
      {#each [1, 2, 3, 4] as r}
        <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {rankFilter === r ? 'chip-blue' : ''}" onclick={() => (rankFilter = r)}>{r}</button>
      {/each}
    </div>
    <span class="text-[11px] text-ink-dim ml-auto tabular-nums">{$t('web.wiki.passives_count', { count: filtered.length })}</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center flex-1"><Spinner /></div>
  {:else}
    <div class="flex-1 overflow-y-auto">
      <table class="w-full text-xs">
        <thead class="bg-bg-deep sticky top-0 z-10">
          <tr class="border-b-2 border-line/40">
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none hover:text-ink-primary transition-fast" onclick={() => toggleSort('name')}>
              {$t('web.wiki.col_name')} {sortKey === 'name' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none hover:text-ink-primary transition-fast" onclick={() => toggleSort('rank')}>
              {$t('web.wiki.col_rank')} {sortKey === 'rank' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.wiki.col_effects')}</th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.wiki.col_description')}</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as p}
            <tr class="border-b border-line/20 hover:bg-bg-hover transition-fast">
              <td class="px-3 py-2">
                <span class="font-medium text-ink-primary">{p.name}</span>
                <span class="text-[10px] text-ink-dim font-mono ml-1">{p.asset}</span>
              </td>
              <td class="px-3 py-2 text-right">
                <span class="chip text-[10px] {p.rank >= 3 ? 'chip-amber' : p.rank >= 2 ? 'chip-blue' : ''}">Lv.{p.rank}</span>
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1">
                  {#each renderEffects(p) as effect}
                    <span class="chip {effect.includes('+') ? 'chip-green' : ''} text-[10px]">{effect}</span>
                  {/each}
                </div>
              </td>
              <td class="px-3 py-2 text-ink-muted max-w-[250px] truncate">{p.description}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
