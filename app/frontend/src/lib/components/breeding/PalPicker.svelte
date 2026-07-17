<script lang="ts">
  // Searchable pal selector. Loads the breedable-pal list once (cached in a
  // module-level promise so multiple pickers on one page share the fetch),
  // renders a dropdown with icon + name + element chips, and emits the chosen
  // tribe via onselect.
  import { onMount } from 'svelte';
  import { clickOutside } from '$lib/utils/clickOutside';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import type { BreedablePal } from '$types/index';
  import Spinner from '$components/ui/Spinner.svelte';

  let {
    value = null,
    placeholder = 'Select a pal…',
    onselect,
    exclude = [],
  }: {
    value?: string | null;
    placeholder?: string;
    onselect?: (tribe: string, pal: BreedablePal) => void;
    exclude?: string[];
  } = $props();

  let open = $state(false);
  let query = $state('');
  let pals = $state<BreedablePal[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const res = await api.breedingPals();
      pals = res.pals;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  const excludeSet = $derived(new Set(exclude));
  const filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    let result = pals;
    if (q) {
      result = result.filter(
        (p) => p.display_name.toLowerCase().includes(q) || p.tribe.toLowerCase().includes(q)
      );
    }
    if (excludeSet.size) {
      result = result.filter((p) => !excludeSet.has(p.tribe));
    }
    return result;
  });

  const selectedPal = $derived(pals.find((p) => p.tribe === value) || null);

  function pick(p: BreedablePal) {
    open = false;
    query = '';
    onselect?.(p.tribe, p);
  }
</script>

<div class="relative" use:clickOutside={() => (open = false)}>
  <button
    type="button"
    class="input flex items-center gap-2 text-left cursor-pointer hover:border-accent/50 transition-fast"
    onclick={() => (open = !open)}
  >
    {#if selectedPal}
      <img
        src={assetUrl(selectedPal.icon)}
        alt={selectedPal.display_name}
        class="w-5 h-5 object-contain rounded-2 bg-bg-deep"
        onerror={imgOnError}
      />
      <span class="text-xs font-medium text-ink-primary truncate flex-1">
        {selectedPal.display_name}
      </span>
    {:else}
      <Icon icon="lucide:search" width={14} class="text-ink-dim" />
      <span class="text-xs text-ink-dim flex-1">{placeholder}</span>
    {/if}
    <Icon icon="lucide:chevron-down" width={14} class="text-ink-dim shrink-0" />
  </button>

  {#if open}
    <div
      class="absolute z-50 mt-1 w-full bg-bg-card border border-line/60 rounded-4 shadow-xl flex flex-col max-h-80"
    >
      <div class="p-2 border-b border-line/40">
        <input
          type="text"
          bind:value={query}
          placeholder="Search pals…"
          class="input text-xs"
          autocomplete="off"
        />
      </div>
      <div class="overflow-y-auto flex-1">
        {#if loading}
          <div class="flex justify-center py-6"><Spinner /></div>
        {:else if error}
          <p class="text-xs text-rose-400 p-3">{error}</p>
        {:else if filtered.length === 0}
          <p class="text-xs text-ink-dim p-3 text-center">No matches</p>
        {:else}
          {#each filtered as pal (pal.tribe)}
            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-bg-hover transition-fast {pal.tribe ===
              value
                ? 'bg-accent/15'
                : ''}"
              onclick={() => pick(pal)}
            >
              <img
                src={assetUrl(pal.icon)}
                alt={pal.display_name}
                class="w-5 h-5 object-contain rounded-2 bg-bg-deep shrink-0"
                onerror={imgOnError}
                loading="lazy"
              />
              <span class="font-medium text-ink-primary truncate flex-1">{pal.display_name}</span>
              <span class="text-[9px] text-ink-dim font-mono shrink-0">R{pal.rarity}</span>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>
