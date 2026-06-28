<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface Skill {
    name: string; asset: string; element: string; power: number;
    cooldown: number; description: string; category: string;
    min_range: number; max_range: number;
  }

  interface ElementInfo {
    name: string; display: string; color: string;
    icons: { passive_base: string; large: string; palstatus: string; small: string };
  }

  let skills = $state<Skill[]>([]);
  let elementMap = $state<Record<string, ElementInfo>>({});
  let loading = $state(true);
  let search = $state('');
  let elementFilter = $state('All');
  let sortKey = $state<'name' | 'power' | 'cooldown'>('name');
  let sortAsc = $state(true);

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/skills');
      const json = await res.json();
      const elList = json.data.elements as ElementInfo[];
      for (const e of elList) elementMap[e.name] = e;
      skills = (json.data.skills as Skill[]).filter((s: Skill) => s.name && s.name !== 'None');
    } catch { /* ignore */ }
    finally { loading = false; }
  });

  const elementNames = $derived(['All', ...Object.keys(elementMap)]);

  const filtered = $derived.by(() => {
    let result = skills;
    if (elementFilter !== 'All') result = result.filter((s) => s.element === elementFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((s) => s.name.toLowerCase().includes(q) || s.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'power') cmp = a.power - b.power;
      else if (sortKey === 'cooldown') cmp = a.cooldown - b.cooldown;
      return sortAsc ? cmp : -cmp;
    });
  });

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }
</script>

<div class="flex flex-col h-full gap-3">
  <div class="flex items-center gap-3 flex-wrap">
    <div class="relative flex-1 max-w-xs">
      <Icon icon="lucide:search" width={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder="Search skills..." class="input pl-8 text-xs" />
    </div>
    <div class="flex gap-1 flex-wrap items-center">
      <span class="text-[10px] text-ink-dim font-semibold uppercase tracking-wider mr-1">Element:</span>
      {#each elementNames as el}
        <button class="chip text-[10px] cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {elementFilter === el ? 'chip-blue' : ''}" onclick={() => (elementFilter = el)}>
          {el === 'All' ? 'All' : ''}
          {#if el !== 'All' && elementMap[el]}
            <img src={assetUrl(elementMap[el].icons.small)} alt={el} class="w-3.5 h-3.5 inline" onerror={imgOnError} loading="lazy" />
          {/if}
          {el !== 'All' ? elementMap[el]?.display || el : ''}
        </button>
      {/each}
    </div>
    <span class="text-[11px] text-ink-dim ml-auto tabular-nums">{filtered.length} skills</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center flex-1"><Spinner /></div>
  {:else}
    <div class="flex-1 overflow-y-auto">
      <table class="w-full text-xs">
        <thead class="bg-bg-deep sticky top-0 z-10">
          <tr class="border-b-2 border-line/40">
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none hover:text-ink-primary transition-fast" onclick={() => toggleSort('name')}>
              Name {sortKey === 'name' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Element</th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none hover:text-ink-primary transition-fast" onclick={() => toggleSort('power')}>
              Power {sortKey === 'power' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-right px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider cursor-pointer select-none hover:text-ink-primary transition-fast" onclick={() => toggleSort('cooldown')}>
              Cooldown {sortKey === 'cooldown' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Category</th>
            <th class="text-left px-3 py-2 text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Description</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as skill}
            {@const elInfo = elementMap[skill.element]}
            <tr class="border-b border-line/20 hover:bg-bg-hover transition-fast">
              <td class="px-3 py-2">
                <span class="font-medium text-ink-primary">{skill.name}</span>
                <span class="text-[10px] text-ink-dim font-mono ml-1">{skill.asset}</span>
              </td>
              <td class="px-3 py-2">
                {#if elInfo}
                  <img src={assetUrl(elInfo.icons.small)} alt={skill.element} class="w-4 h-4 inline" title={elInfo.display} onerror={imgOnError} loading="lazy" />
                {:else}
                  <span class="chip text-[10px]">{skill.element}</span>
                {/if}
              </td>
              <td class="px-3 py-2 text-right tabular-nums font-semibold">{skill.power}</td>
              <td class="px-3 py-2 text-right tabular-nums">{skill.cooldown}s</td>
              <td class="px-3 py-2"><span class="chip text-[10px]">{skill.category}</span></td>
              <td class="px-3 py-2 text-ink-muted max-w-[300px] truncate">{skill.description}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
