<script lang="ts">
  // The vertical 5-slot Party column. Renders PalPartyCards for occupied slots
  // and empty-slot placeholders up to PARTY_CAPACITY, so the column always shows
  // the full party shape (matches PSP's party sidebar).
  import { t } from '$stores/index';
  import PalPartyCard from './PalPartyCard.svelte';
  import type { PalSummary } from '$types/index';

  let {
    pals,
    selectedIds = [],
    playerLevel = 0,
    onclick,
    onselect,
    onswap,
  }: {
    pals: PalSummary[];
    selectedIds?: string[];
    playerLevel?: number;
    onclick?: (pal: PalSummary) => void;
    onselect?: (pal: PalSummary) => void;
    onswap?: (sourceId: string, targetId: string) => void;
  } = $props();

  const PARTY_CAPACITY = 5;
  // Pad to 5 slots with nulls so empty slots render as placeholders.
  const slots = $derived.by(() => {
    const sorted = [...pals].sort((a, b) => (a.slot_index ?? 0) - (b.slot_index ?? 0));
    const out: (PalSummary | null)[] = [...sorted];
    while (out.length < PARTY_CAPACITY) out.push(null);
    return out.slice(0, PARTY_CAPACITY);
  });
</script>

<div class="space-y-2">
  <div class="flex items-center justify-between px-1">
    <h3 class="text-[11px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.pal_editor.party_zone')}</h3>
    <span class="text-[10px] text-ink-muted">{pals.length}/{PARTY_CAPACITY}</span>
  </div>
  {#each slots as pal, i (pal?.instance_id ?? `empty-${i}`)}
    {#if pal}
      <PalPartyCard
        {pal}
        selected={selectedIds.includes(pal.instance_id)}
        {playerLevel}
        {onclick}
        {onselect}
        {onswap}
      />
    {:else}
      <div class="w-full rounded-4 border-2 border-dashed border-line/30 p-2 h-[68px] flex items-center justify-center">
        <span class="text-[10px] text-ink-dim">—</span>
      </div>
    {/if}
  {/each}
</div>
