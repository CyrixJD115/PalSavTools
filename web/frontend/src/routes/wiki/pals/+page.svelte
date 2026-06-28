<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface Pal {
    name: string; asset: string; icon: string; description?: string;
    elements?: Record<string, { name: string; icon: string; icon_large: string }>;
    stats?: Record<string, number>; scaling?: Record<string, number>;
    work_suitabilities?: Record<string, number>;
    partner_skill?: string;
  }

  let pals = $state<Pal[]>([]);
  let loading = $state(true);
  let search = $state('');
  let selected = $state<Pal | null>(null);
  let elementFilter = $state('All');

  onMount(async () => {
    try {
      const res = await fetch('/api/data/game-data/characters');
      const json = await res.json();
      pals = json.data.pals.filter((p: Pal) => p.name && p.elements && Object.keys(p.elements).length > 0);
    } catch (e) { console.error('Pals wiki load failed:', e); }
    finally { loading = false; }
  });

  const elements = $derived.by(() => {
    const set = new Set<string>();
    for (const p of pals) {
      for (const el of Object.keys(p.elements ?? {})) set.add(el);
    }
    return ['All', ...set];
  });

  const filtered = $derived.by(() => {
    let result = pals;
    if (elementFilter !== 'All') {
      result = result.filter((p) => p.elements?.[elementFilter]);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q) || p.asset.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => a.name.localeCompare(b.name));
  });
</script>

<div class="flex h-full gap-4">
  <div class="w-64 shrink-0 flex flex-col bg-bg-deep/25 rounded-4 p-2">
    <div class="flex items-center justify-between mb-2 px-1">
      <span class="text-[11px] text-ink-dim font-semibold tracking-wide uppercase">{filtered.length} entries</span>
    </div>
    <div class="relative mb-3 px-1">
      <Icon icon="lucide:search" width={14} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-dim" />
      <input type="text" bind:value={search} placeholder="Search pals..." class="input pl-8 text-xs" />
    </div>
    <div class="flex flex-wrap gap-1 mb-3 px-1">
      {#each elements as el}
        <button
          class="chip text-[10px] px-2 py-0.5 cursor-pointer hover:bg-bg-hover hover:border-line/80 transition-fast {elementFilter === el ? 'chip-blue' : ''}"
          onclick={() => (elementFilter = el)}
        >{el === 'All' ? 'All' : el}</button>
      {/each}
    </div>
    <div class="flex-1 overflow-y-auto space-y-0.5">
      {#each filtered as pal}
        <button
          class="flex w-full items-center gap-2 px-2.5 py-1.5 rounded-4 text-left text-xs transition-all {selected?.asset === pal.asset ? 'bg-accent/15 border-2 border-accent/30' : 'hover:bg-bg-hover border-2 border-transparent'}"
          onclick={() => (selected = pal)}
        >
          <img src={assetUrl(pal.icon)} alt={pal.name} class="w-6 h-6 shrink-0 object-contain rounded-2 bg-bg-deep" onerror={imgOnError} loading="lazy" />
          <span class="font-medium text-ink-primary truncate flex-1">{pal.name}</span>
          <div class="flex gap-0.5 shrink-0">
            {#each Object.values(pal.elements ?? {}) as el}
              <img src={assetUrl(el.icon)} alt={el.name} class="w-3.5 h-3.5" title={el.name} onerror={imgOnError} loading="lazy" />
            {/each}
          </div>
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
          <img src={assetUrl(selected.icon)} alt={selected.name} class="w-16 h-16 object-contain rounded-4 bg-bg-deep border-2 border-line/30" onerror={imgOnError} />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <h2 class="text-lg font-bold text-ink-emphasis">{selected.name}</h2>
              <div class="flex gap-1">
                {#each Object.values(selected.elements ?? {}) as el}
                  <img src={assetUrl(el.icon)} alt={el.name} class="w-5 h-5" title={el.name} onerror={imgOnError} loading="lazy" />
                {/each}
              </div>
            </div>
            <span class="text-[11px] text-ink-dim font-mono">{selected.asset}</span>
          </div>
        </div>

        <p class="text-xs text-ink-secondary leading-relaxed">{selected.description ?? ''}</p>

        {#if Object.keys(selected.stats ?? {}).length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Base Stats</h3>
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {#each Object.entries(selected.stats ?? {}) as [key, val]}
                <div class="bg-bg-deep border-2 border-line/40 rounded-4 px-3 py-2">
                  <p class="text-[10px] text-ink-dim uppercase tracking-wide">{key.replace(/_/g, ' ')}</p>
                  <p class="text-sm font-bold text-ink-emphasis tabular-nums">{val}</p>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if Object.keys(selected.work_suitabilities ?? {}).length}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Work Suitability</h3>
            <div class="flex flex-wrap gap-1.5">
              {#each Object.entries(selected.work_suitabilities ?? {}) as [key, val]}
                {#if val > 0}
                  <span class="chip chip-amber text-[10px]">{key.replace(/([A-Z])/g, ' $1').trim()} <span class="font-bold">Lv.{val}</span></span>
                {/if}
              {/each}
            </div>
          </div>
        {/if}

        {#if selected.partner_skill}
          <div>
            <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Partner Skill</h3>
            <span class="chip chip-green text-[10px]">{selected.partner_skill}</span>
          </div>
        {/if}
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-ink-dim gap-2">
        <Icon icon="lucide:egg" width={32} class="text-ink-muted" />
        <p class="text-xs">Select a Pal to view details</p>
      </div>
    {/if}
  </div>
</div>
