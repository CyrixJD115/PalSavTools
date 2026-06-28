<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface WorkType {
    id: string; display_name: string; icon: string; index: number;
  }

  interface Pal {
    name: string; asset: string; icon: string;
    elements?: Record<string, unknown>;
    work_suitabilities?: Record<string, number>;
  }

  let workTypes = $state<WorkType[]>([]);
  let pals = $state<Pal[]>([]);
  let loading = $state(true);
  let selected = $state<string | null>(null);

  onMount(async () => {
    try {
      const [wsRes, charsRes] = await Promise.all([
        fetch('/api/data/game-data/work_suitability'),
        fetch('/api/data/game-data/characters'),
      ]);
      const wsJson = await wsRes.json();
      const charsJson = await charsRes.json();
      workTypes = (wsJson.data.work_types as WorkType[]).filter((w: WorkType) => w.display_name);
      pals = (charsJson.data.pals as Pal[]).filter((p: Pal) => p.name && p.elements && Object.keys(p.elements).length > 0);
    } catch { /* ignore */ }
    finally { loading = false; }
  });

  const selectedPals = $derived.by(() => {
    const sel = selected;
    if (!sel) return [];
    return pals
      .filter((p) => (p.work_suitabilities?.[sel] ?? 0) > 0)
      .map((p) => ({ name: p.name, icon: p.icon, level: p.work_suitabilities?.[sel] ?? 0 }))
      .sort((a, b) => b.level - a.level || a.name.localeCompare(b.name));
  });

  const selectedWork = $derived(workTypes.find((w) => w.id === selected));
</script>

<div class="flex h-full gap-4">
  <div class="w-64 shrink-0 flex flex-col bg-bg-deep/25 rounded-4 p-2">
    <div class="flex-1 overflow-y-auto space-y-0.5">
      {#each workTypes as wt}
        <button
          class="flex w-full items-center gap-2 px-2.5 py-1.5 rounded-4 text-left text-xs transition-all {selected === wt.id ? 'bg-accent/15 border-2 border-accent/30' : 'hover:bg-bg-hover border-2 border-transparent'}"
          onclick={() => (selected = wt.id)}
        >
          <img src={assetUrl(wt.icon)} alt={wt.display_name} class="w-5 h-5 shrink-0" onerror={imgOnError} loading="lazy" />
          <span class="font-medium text-ink-primary">{wt.display_name}</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="flex items-center justify-center h-full"><Spinner /></div>
    {:else if selectedWork && selected}
      <div class="card space-y-4">
        <div class="flex items-center gap-3">
          <img src={assetUrl(selectedWork.icon)} alt={selectedWork.display_name} class="w-10 h-10 shrink-0" onerror={imgOnError} />
          <div>
            <h2 class="text-lg font-bold text-ink-emphasis">{selectedWork.display_name}</h2>
            <span class="chip chip-blue text-[10px]">{selectedWork.id}</span>
          </div>
        </div>

        <div>
          <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">Pals ({selectedPals.length})</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
            {#each selectedPals as pal}
              <div class="bg-bg-deep border-2 border-line/30 rounded-4 px-3 py-1.5 flex items-center gap-2">
                <img src={assetUrl(pal.icon)} alt={pal.name} class="w-8 h-8 object-contain rounded-2" onerror={imgOnError} loading="lazy" />
                <span class="font-medium text-ink-primary text-xs flex-1">{pal.name}</span>
                <span class="chip chip-amber text-[10px]">Lv.{pal.level}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-ink-dim gap-2">
        <Icon icon="lucide:hammer" width={32} class="text-ink-muted" />
        <p class="text-xs">Select a work type to view details</p>
      </div>
    {/if}
  </div>
</div>
