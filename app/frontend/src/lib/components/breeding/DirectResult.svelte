<script lang="ts">
  // Renders one Direct-Mode result row: [Parent A] + [Parent B] → [Child].
  // Used for both the single forward answer and each reverse-mode candidate.
  // Needs the breedable-pal lookup to resolve tribes → display names + icons,
  // passed in from the page (which already loaded it) to avoid re-fetching.
  import type { BreedablePal, DirectResultItem } from '$types/index';
  import Icon from '@iconify/svelte';
  import PalSlot from './PalSlot.svelte';

  let {
    result,
    palMap,
  }: { result: DirectResultItem; palMap: Map<string, BreedablePal> } = $props();

  const palA = $derived(palMap.get(result.parent_a));
  const palB = $derived(palMap.get(result.parent_b));
  const palChild = $derived(palMap.get(result.child));

  // Prefer the result's enriched fields (display/icon already set by backend),
  // fall back to the palMap lookup.
  const childDisplay = $derived(result.child_display || palChild?.display_name || result.child);
  const childIcon = $derived(result.child_icon || palChild?.icon || null);
</script>

<div class="flex items-center gap-3 p-3 rounded-4 bg-bg-deep/40 border border-line/30 hover:border-line/60 transition-fast">
  <PalSlot tribe={result.parent_a} display={palA?.display_name} icon={palA?.icon} size="sm" />

  <Icon icon="lucide:plus" width={14} class="text-ink-dim shrink-0" />

  <PalSlot tribe={result.parent_b} display={palB?.display_name} icon={palB?.icon} size="sm" />

  <Icon icon="lucide:arrow-right" width={16} class="text-accent shrink-0" />

  <div class="flex items-center gap-2 min-w-0 flex-1">
    <PalSlot tribe={result.child} display={childDisplay} icon={childIcon} size="md" />
    {#if result.combo_type === 'unique'}
      <span class="chip chip-amber text-[9px] px-1.5 py-0 shrink-0">Special</span>
    {/if}
  </div>

  {#if result.child_gender_prob}
    <div class="flex items-center gap-1 shrink-0 text-[10px]">
      {#if result.child_gender_prob.male > 0}
        <span class="text-sky-400" title="Male probability">
          <Icon icon="lucide:mars" width={11} />
          {Math.round(result.child_gender_prob.male * 100)}%
        </span>
      {/if}
      {#if result.child_gender_prob.female > 0}
        <span class="text-pink-400" title="Female probability">
          <Icon icon="lucide:venus" width={11} />
          {Math.round(result.child_gender_prob.female * 100)}%
        </span>
      {/if}
    </div>
  {/if}
</div>
