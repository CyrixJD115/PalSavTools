<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  interface ElementData {
    name: string; display: string; color: string; index: number;
    icons: { passive_base: string; large: string; palstatus: string; small: string };
  }

  interface Pal {
    name: string; asset: string;
    icon: string;
    elements: Record<string, { name: string; icon: string }>;
  }

  let elements = $state<ElementData[]>([]);
  let pals = $state<Pal[]>([]);
  let loading = $state(true);
  let selected = $state<ElementData | null>(null);

  onMount(async () => {
    try {
      const [skillsRes, charsRes] = await Promise.all([
        fetch('/api/data/game-data/skills'),
        fetch('/api/data/game-data/characters'),
      ]);
      const skillsJson = await skillsRes.json();
      const charsJson = await charsRes.json();
      elements = (skillsJson.data.elements as ElementData[]).filter((e: ElementData) => e.name);
      pals = (charsJson.data.pals as Pal[]).filter((p: Pal) => p.name && p.elements && Object.keys(p.elements).length > 0);
    } catch { /* ignore */ }
    finally { loading = false; }
  });

  const selectedPals = $derived.by(() => {
    if (!selected) return [];
    return pals
      .filter((p) => selected && p.elements?.[selected.name])
      .sort((a, b) => a.name.localeCompare(b.name));
  });
</script>

<div class="flex h-full gap-4">
  <div class="w-64 shrink-0 flex flex-col bg-bg-deep/25 rounded-4 p-2">
    <div class="flex-1 overflow-y-auto space-y-0.5">
      {#each elements as el}
        <button
          class="flex w-full items-center gap-2 px-2.5 py-1.5 rounded-4 text-left text-xs transition-all {selected?.name === el.name ? 'bg-accent/15 border-2 border-accent/30' : 'hover:bg-bg-hover border-2 border-transparent'}"
          onclick={() => (selected = el)}
        >
          <img src={assetUrl(el.icons.small)} alt={el.display} class="w-5 h-5 shrink-0" onerror={imgOnError} loading="lazy" />
          <span class="font-medium text-ink-primary">{el.display || el.name}</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="flex items-center justify-center h-full"><Spinner /></div>
    {:else if selected}
      <div class="card space-y-4">
        <div class="flex items-center gap-4">
          <img src={assetUrl(selected.icons.large)} alt={selected.display} class="w-14 h-14 shrink-0" onerror={imgOnError} />
          <div>
            <h2 class="text-lg font-bold" style="color: {selected.color}">{selected.display || selected.name}</h2>
            <span class="text-[11px] text-ink-dim font-mono">{selected.name}</span>
          </div>
        </div>

        <div>
          <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.wiki.pals_count', { count: selectedPals.length })}</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
            {#each selectedPals as pal}
              <div class="bg-bg-deep border-2 border-line/30 rounded-4 px-3 py-1.5 flex items-center gap-2">
                <img src={assetUrl(pal.icon)} alt={pal.name} class="w-8 h-8 object-contain rounded-2" onerror={imgOnError} loading="lazy" />
                <span class="font-medium text-ink-primary text-xs flex-1">{pal.name}</span>
                <div class="flex gap-0.5">
                  {#each Object.values(pal.elements ?? {}) as el}
                    <img src={assetUrl(el.icon)} alt={el.name} class="w-3.5 h-3.5" title={el.name} onerror={imgOnError} loading="lazy" />
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full text-ink-dim gap-2">
        <Icon icon="lucide:flame" width={32} class="text-ink-muted" />
        <p class="text-xs">{$t('web.wiki.select_element')}</p>
      </div>
    {/if}
  </div>
</div>
