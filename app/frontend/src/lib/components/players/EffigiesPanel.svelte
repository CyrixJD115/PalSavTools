<script lang="ts">
  // Effigies editor — grid/list view with relics sorted by icon index (00-12).
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import Spinner from '$components/ui/Spinner.svelte';
  import Button from '$components/ui/Button.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import { relicIconPath } from '$lib/utils/relicIconMap';
  import type { RelicEntry } from '$types/index';

  // The display order matches the icon file numbering (00-12), which is the
  // same order the effigies unlock in-game. Sorted by this index so the GUI
  // always shows Lifmunk first, Mimog last, regardless of backend order.
  const ICON_ORDER: Record<string, number> = {
    "EPalRelicType::CapturePower": 0,
    "EPalRelicType::HungerReduction": 1,
    "EPalRelicType::SwimSpeed": 2,
    "EPalRelicType::FoodDecayReduction": 3,
    "EPalRelicType::JumpPower": 4,
    "EPalRelicType::GliderSpeed": 5,
    "EPalRelicType::ClimbSpeed": 6,
    "EPalRelicType::StatusAilmentResist": 7,
    "EPalRelicType::StaminaReduction": 8,
    "EPalRelicType::SphereHoming": 9,
    "EPalRelicType::ExpBonus": 10,
    "EPalRelicType::RainbowPassiveRate": 11,
    "EPalRelicType::MoveSpeed": 12,
  };

  type ViewMode = 'list' | 'grid';

  let { uid }: { uid: string } = $props();

  let relics = $state<RelicEntry[]>([]);
  let relicValues = $state<Record<string, number>>({});
  let supported = $state(true);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saving = $state(false);
  let viewMode = $state<ViewMode>('grid');

  onMount(() => { void load(); });

  async function load() {
    loading = true; error = null;
    try {
      const resp = await api.playerAbilities(uid);
      relics = resp.relics;
      supported = resp.supported;
      relicValues = Object.fromEntries(resp.relics.map((r) => [r.type, r.count]));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  // Sort relics by icon index 00-12 so the GUI always displays in the correct
  // game order regardless of backend response order.
  const sortedRelics = $derived(
    [...relics].sort((a, b) => (ICON_ORDER[a.type] ?? 99) - (ICON_ORDER[b.type] ?? 99)),
  );

  function setAllToMax() {
    for (const r of relics) relicValues[r.type] = r.cumulative_max;
    relicValues = { ...relicValues };
  }

  async function apply() {
    saving = true;
    try {
      await api.setPlayerAbilities(uid, { values: relicValues });
      toast.success($t('web.players.effigies_apply', 'Effigies updated.'));
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      saving = false;
    }
  }

  function relicIndex(relicType: string): string {
    const idx = ICON_ORDER[relicType];
    return idx !== undefined ? String(idx).padStart(2, '0') : '--';
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else}
  <div class="p-5 max-w-2xl mx-auto space-y-4">
    <!-- header with view toggle -->
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:gem" width={12} class="inline mr-1.5 text-accent" />
        {$t('web.players.edit_effigies', 'Effigies')}
        {#if relics.length}
          <span class="text-ink-muted font-normal normal-case">— {relics.length}</span>
        {/if}
      </p>
      <div class="flex items-center gap-1.5">
        <!-- view toggle -->
        <div class="flex items-center gap-0.5 p-0.5 rounded-2 bg-bg-deep border border-line/30">
          <button
            type="button"
            class="p-1 rounded-1.5 transition-fast {viewMode === 'grid' ? 'bg-bg-surface shadow-sm text-ink-primary' : 'text-ink-dim hover:text-ink-secondary'}"
            onclick={() => (viewMode = 'grid')}
            aria-label="Grid view"
          >
            <Icon icon="lucide:grid-3x3" width={13} />
          </button>
          <button
            type="button"
            class="p-1 rounded-1.5 transition-fast {viewMode === 'list' ? 'bg-bg-surface shadow-sm text-ink-primary' : 'text-ink-dim hover:text-ink-secondary'}"
            onclick={() => (viewMode = 'list')}
            aria-label="List view"
          >
            <Icon icon="lucide:list" width={13} />
          </button>
        </div>
        <div class="w-px h-4 bg-line/30"></div>
        <Button variant="ghost" onclick={setAllToMax} disabled={!supported || saving} class="!text-xs">
          <Icon icon="lucide:zap" width={13} class="mr-1" />
          {$t('web.players.max_all_abilities', 'Max All')}
        </Button>
      </div>
    </div>

    {#if !supported}
      <p class="text-xs text-status-warning">{$t('web.players.effigies_unsupported')}</p>
    {/if}

    {#if sortedRelics.length === 0}
      <EmptyState icon="lucide:gem" title={$t('web.players.edit_effigies', 'Effigies')} class="py-8">
        <p class="text-xs">{$t('web.players.effigies_unsupported')}</p>
      </EmptyState>
    {:else if viewMode === 'list'}
      <!-- ─── LIST VIEW ─── -->
      <div class="space-y-1">
        {#each sortedRelics as r (r.type)}
          <div transition:fade={{ duration: 120 }} class="flex items-center gap-2 py-1.5 px-1 rounded-2 hover:bg-bg-hover/40 transition-fast group">
            <img src={assetUrl(relicIconPath(r.type))} alt={r.label} onerror={imgOnError} class="w-6 h-6 rounded object-contain shrink-0" loading="lazy" />
            <span class="text-[9px] text-ink-dim tabular-nums font-mono w-5 shrink-0">#{relicIndex(r.type)}</span>
            <div class="flex-1 min-w-0">
              <p class="text-xs text-ink-primary leading-tight truncate">{r.label}</p>
              <p class="text-[9px] text-ink-dim leading-tight">
                {$t('web.players.effigies_rank_hint', { rank: r.rank, max: r.max_rank })}
              </p>
            </div>
            <input
              class="w-16 bg-bg-deep border border-line/40 rounded-2 px-1.5 py-1 text-xs text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent transition-fast"
              type="number"
              min="0"
              max={r.cumulative_max}
              bind:value={relicValues[r.type]}
              disabled={!supported || saving}
            />
            <span class="text-[9px] text-ink-dim tabular-nums w-6 text-right shrink-0">/{r.cumulative_max}</span>
          </div>
        {/each}
      </div>
    {:else}
      <!-- ─── GRID VIEW ─── -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {#each sortedRelics as r (r.type)}
          <div transition:fade={{ duration: 120 }} class="flex items-center gap-3 p-2.5 rounded-4 bg-bg-deep/40 border border-line/30 hover:bg-bg-hover/40 transition-fast">
            <img src={assetUrl(relicIconPath(r.type))} alt={r.label} onerror={imgOnError} class="w-10 h-10 rounded-lg object-contain shrink-0" loading="lazy" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] text-ink-dim tabular-nums font-mono">#{relicIndex(r.type)}</span>
                <p class="text-xs text-ink-primary truncate">{r.label}</p>
              </div>
              <p class="text-[9px] text-ink-dim leading-tight mt-0.5">
                {$t('web.players.effigies_rank_hint', { rank: r.rank, max: r.max_rank })}
              </p>
              <div class="flex items-center gap-1.5 mt-1.5">
                <input
                  class="w-full bg-bg-surface border border-line/40 rounded-2 px-1.5 py-1 text-xs text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent transition-fast"
                  type="number"
                  min="0"
                  max={r.cumulative_max}
                  bind:value={relicValues[r.type]}
                  disabled={!supported || saving}
                />
                <span class="text-[9px] text-ink-dim tabular-nums shrink-0">/{r.cumulative_max}</span>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <!-- footer -->
    <div class="flex items-center gap-2 pt-2 border-t border-line/20">
      <Button variant="primary" onclick={apply} disabled={!supported || saving}>
        <Icon icon="lucide:check" width={14} class="mr-1" />
        {$t('web.players.effigies_apply', 'Apply Effigies')}
      </Button>
      <Button variant="ghost" onclick={() => void load()} disabled={loading || saving}>
        <Icon icon="lucide:refresh-cw" width={13} class="mr-1" />
        {$t('web.common.refresh', 'Refresh')}
      </Button>
    </div>
  </div>
{/if}
