<script lang="ts">
  // Hover detail overlay for a PalTile — IVs, souls, passives at a glance.
  // Kept out of the tile itself to preserve grid density (PSP convention).
  import Icon from '@iconify/svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import type { PalSummary } from '$types/index';

  let { pal }: { pal: PalSummary } = $props();

  const iv = (v: number) =>
    v >= 90 ? 'text-status-success' : v >= 70 ? 'text-yellow-400' : 'text-ink-muted';
</script>

<div class="w-64 bg-bg-surface border-2 border-line/60 rounded-6 shadow-card-lg p-3 space-y-2">
  <!-- header -->
  <div class="flex items-center gap-2">
    <img src={assetUrl(pal.icon)} alt="" class="w-10 h-10 rounded-4 bg-bg-deep object-cover" onerror={imgOnError} />
    <div class="min-w-0">
      <p class="text-sm font-bold text-ink-primary truncate">{pal.display_name ?? pal.character_id}</p>
      {#if pal.nickname}<p class="text-[10px] text-ink-muted truncate">"{pal.nickname}"</p>{/if}
    </div>
  </div>

  <!-- IVs -->
  <div>
    <p class="text-[9px] font-semibold text-ink-dim uppercase tracking-wider mb-1">IVs</p>
    <div class="grid grid-cols-3 gap-1 text-xs">
      <span class="flex items-center gap-1 bg-bg-deep rounded-3 px-1.5 py-0.5 {iv(pal.talent_hp)}">
        <Icon icon="lucide:heart" width={11} />{pal.talent_hp}
      </span>
      <span class="flex items-center gap-1 bg-bg-deep rounded-3 px-1.5 py-0.5 {iv(pal.talent_shot)}">
        <Icon icon="lucide:sword" width={11} />{pal.talent_shot}
      </span>
      <span class="flex items-center gap-1 bg-bg-deep rounded-3 px-1.5 py-0.5 {iv(pal.talent_defense)}">
        <Icon icon="lucide:shield" width={11} />{pal.talent_defense}
      </span>
    </div>
  </div>

  <!-- Souls -->
  <div>
    <p class="text-[9px] font-semibold text-ink-dim uppercase tracking-wider mb-1">Souls</p>
    <div class="grid grid-cols-4 gap-1 text-[11px] text-ink-secondary">
      <span class="bg-bg-deep rounded-3 px-1 py-0.5 text-center">HP {pal.rank_hp}</span>
      <span class="bg-bg-deep rounded-3 px-1 py-0.5 text-center">AT {pal.rank_attack}</span>
      <span class="bg-bg-deep rounded-3 px-1 py-0.5 text-center">DF {pal.rank_defense}</span>
      <span class="bg-bg-deep rounded-3 px-1 py-0.5 text-center">WS {pal.rank_craftspeed}</span>
    </div>
  </div>

  <!-- Passives -->
  {#if pal.passive_skills.length}
    <div>
      <p class="text-[9px] font-semibold text-ink-dim uppercase tracking-wider mb-1">Passives</p>
      <div class="flex flex-wrap gap-1">
        {#each pal.passive_skills.slice(0, 4) as skill}
          <span class="chip chip-green text-[9px] px-1.5 py-0">{skill}</span>
        {/each}
      </div>
    </div>
  {/if}
</div>
