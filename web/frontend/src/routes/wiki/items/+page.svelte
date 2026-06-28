<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface Item {
    name: string; asset: string; icon: string; description?: string;
    type_a_display?: string; rarity?: number; weight?: number; price?: number;
    max_stack?: number;
  }

  let items = $state<Item[]>([]);
  let loading = $state(true);
  let search = $state('');
  let typeFilter = $state('All');
  let sortKey = $state<'name' | 'price' | 'weight'>('name');
  let sortAsc = $state(true);

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/items');
      const json = await res.json();
      items = json.data.items?.filter((i: Item) => i.name) ?? [];
    } catch (e) { console.error('Items wiki load failed:', e); }
    finally { loading = false; }
  });

  const types = $derived.by(() => {
    const set = new Set<string>();
    for (const i of items) if (i.type_a_display) set.add(i.type_a_display);
    return ['All', ...set];
  });

  const filtered = $derived.by(() => {
    let result = items;
    if (typeFilter !== 'All') result = result.filter((i) => i.type_a_display === typeFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((i) => i.name.toLowerCase().includes(q) || i.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'price') cmp = (a.price ?? 0) - (b.price ?? 0);
      else if (sortKey === 'weight') cmp = (a.weight ?? 0) - (b.weight ?? 0);
      return sortAsc ? cmp : -cmp;
    });
  });

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }

  const rarityColors: Record<number, string> = { 0: 'text-ink-muted', 1: 'text-green-400', 2: 'text-blue-400', 3: 'text-purple-400', 4: 'text-yellow-400' };
  const rarityLabels: Record<number, string> = { 0: 'Common', 1: 'Uncommon', 2: 'Rare', 3: 'Epic', 4: 'Legendary' };
</script>

<div class="flex flex-col h-full gap-3">
  <div class="flex items-center gap-3 flex-wrap">
    <div class="relative flex-1 max-w-xs">
      <Icon icon="lucide:search" width={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder="Search items..." class="input pl-8 text-xs" />
    </div>
    <div class="flex gap-1 flex-wrap">
      {#each types as t}
        <button class="chip text-[10px] cursor-pointer {typeFilter === t ? 'chip-blue' : ''}" onclick={() => (typeFilter = t)}>{t}</button>
      {/each}
    </div>
    <span class="text-[11px] text-ink-dim ml-auto tabular-nums">{filtered.length} items</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center flex-1"><Spinner /></div>
  {:else}
    <div class="flex-1 overflow-y-auto">
      <table class="w-full text-xs">
        <thead class="bg-bg-deep sticky top-0 z-10">
          <tr class="border-b-2 border-line/40">
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none" onclick={() => toggleSort('name')}>
              Name {sortKey === 'name' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Type</th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Rarity</th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none" onclick={() => toggleSort('weight')}>
              Weight {sortKey === 'weight' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none" onclick={() => toggleSort('price')}>
              Price {sortKey === 'price' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Max Stack</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as item}
            <tr class="border-b border-line/20 hover:bg-bg-hover transition-fast">
              <td class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <img src={assetUrl(item.icon)} alt={item.name} class="w-8 h-8 object-contain shrink-0" onerror={imgOnError} loading="lazy" />
                  <div>
                    <span class="font-medium text-ink-primary">{item.name}</span>
                    <span class="text-[10px] text-ink-dim font-mono block">{item.asset}</span>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2"><span class="chip text-[10px]">{item.type_a_display ?? '-'}</span></td>
              <td class="px-3 py-2"><span class="font-semibold {rarityColors[item.rarity ?? 0] ?? 'text-ink-muted'}">{rarityLabels[item.rarity ?? 0] || 'Common'}</span></td>
              <td class="px-3 py-2 text-right tabular-nums">{item.weight ?? 0}</td>
              <td class="px-3 py-2 text-right tabular-nums">{(item.price ?? 0).toLocaleString()}</td>
              <td class="px-3 py-2 text-right tabular-nums">{item.max_stack ?? 0}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
