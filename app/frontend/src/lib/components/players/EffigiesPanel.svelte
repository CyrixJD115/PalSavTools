<script lang="ts">
  // Effigies editor — the progress bar IS the value editor.
  // Click anywhere on the bar to set the value proportionally.
  // −/+ buttons for ±1 fine adjustment. /max shown after.
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

  function bump(relicType: string, delta: number) {
    const r = relics.find((x) => x.type === relicType);
    if (!r) return;
    const cur = relicValues[relicType] ?? 0;
    relicValues[relicType] = Math.max(0, Math.min(r.cumulative_max, cur + delta));
    relicValues = { ...relicValues };
  }

  function barClick(relicType: string, e: MouseEvent) {
    const r = relics.find((x) => x.type === relicType);
    if (!r || !supported || saving) return;
    const bar = e.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    relicValues[relicType] = Math.round(pct * r.cumulative_max);
    relicValues = { ...relicValues };
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else}
  <div class="p-5 space-y-4">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:gem" width={12} class="inline mr-1.5 text-accent" />
        {$t('web.players.edit_effigies', 'Effigies')}
        {#if relics.length}
          <span class="text-ink-muted font-normal normal-case">— {relics.length}</span>
        {/if}
      </p>
      <div class="flex items-center gap-1.5">
        <div class="flex items-center gap-0.5 p-0.5 rounded-2 bg-bg-deep border border-line/30">
          <button type="button"
            class="p-1 rounded-1.5 transition-fast {viewMode === 'grid' ? 'bg-bg-surface shadow-sm text-ink-primary' : 'text-ink-dim hover:text-ink-secondary'}"
            onclick={() => (viewMode = 'grid')} aria-label="Grid view"
          ><Icon icon="lucide:grid-3x3" width={13} /></button>
          <button type="button"
            class="p-1 rounded-1.5 transition-fast {viewMode === 'list' ? 'bg-bg-surface shadow-sm text-ink-primary' : 'text-ink-dim hover:text-ink-secondary'}"
            onclick={() => (viewMode = 'list')} aria-label="List view"
          ><Icon icon="lucide:list" width={13} /></button>
        </div>
        <div class="w-px h-4 bg-line/30"></div>
        <Button variant="ghost" onclick={setAllToMax} disabled={!supported || saving} class="!text-xs">
          <Icon icon="lucide:zap" width={13} class="mr-1" />{$t('web.players.max_all_abilities', 'Max All')}
        </Button>
      </div>
    </div>

    {#if !supported}
      <p class="text-xs text-status-warning">{$t('web.players.effigies_unsupported')}</p>
    {/if}

    {#if sortedRelics.length === 0}
      <EmptyState icon="lucide:gem" title={$t('web.players.edit_effigies', 'Effigies')} class="py-8" />
    {:else if viewMode === 'list'}
      <!-- ─── LIST VIEW ─── -->
      <div class="space-y-1">
        {#each sortedRelics as r (r.type)}
          {@const val = relicValues[r.type] ?? 0}
          {@const pct = r.cumulative_max > 0 ? (val / r.cumulative_max) * 100 : 0}
          <div transition:fade={{ duration: 120 }} class="flex items-center gap-2 py-1.5 px-1 rounded-2 hover:bg-bg-hover/40 transition-fast">
            <img src={assetUrl(relicIconPath(r.type))} alt={r.label} onerror={imgOnError} class="w-6 h-6 rounded object-contain shrink-0" loading="lazy" />
            <span class="text-[9px] text-ink-dim tabular-nums font-mono w-5 shrink-0">#{relicIndex(r.type)}</span>
            <div class="flex-1 min-w-0">
              <p class="text-xs text-ink-primary leading-tight truncate">{r.label}</p>
              <p class="text-[9px] text-ink-dim leading-tight">{$t('web.players.effigies_rank_hint', { rank: r.rank, max: r.max_rank })}</p>
            </div>
            <button type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover disabled:opacity-30 text-xs leading-none shrink-0 flex items-center justify-center transition-fast"
              onclick={() => bump(r.type, -1)} disabled={!supported || saving || val <= 0}
            >−</button>
            <!-- clickable progress bar -->
            <div class="relative flex-1 h-6 bg-bg-deep rounded-2 border border-line/40 cursor-pointer overflow-hidden"
              role="slider" aria-label={r.label} aria-valuemin="0" aria-valuemax={r.cumulative_max} aria-valuenow={val}
              onclick={(e) => barClick(r.type, e)}
            >
              <div class="h-full rounded-2 transition-all duration-200 {val >= r.cumulative_max ? 'bg-status-success' : 'bg-accent'}" style="width: {pct}%"></div>
              <span class="absolute inset-0 flex items-center justify-center text-[10px] tabular-nums font-semibold text-white pointer-events-none">{val}</span>
            </div>
            <button type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover disabled:opacity-30 text-xs leading-none shrink-0 flex items-center justify-center transition-fast"
              onclick={() => bump(r.type, 1)} disabled={!supported || saving || val >= r.cumulative_max}
            >+</button>
            <span class="text-[9px] text-ink-dim tabular-nums w-8 text-right shrink-0">/{r.cumulative_max}</span>
          </div>
        {/each}
      </div>
    {:else}
      <!-- ─── GRID VIEW ─── -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {#each sortedRelics as r (r.type)}
          {@const val = relicValues[r.type] ?? 0}
          {@const pct = r.cumulative_max > 0 ? (val / r.cumulative_max) * 100 : 0}
          <div transition:fade={{ duration: 120 }} class="p-3 rounded-4 bg-bg-deep/40 border border-line/30 hover:bg-bg-hover/40 transition-fast flex flex-col gap-2.5">
            <div class="flex items-start gap-2.5">
              <img src={assetUrl(relicIconPath(r.type))} alt={r.label} onerror={imgOnError} class="w-9 h-9 rounded-lg object-contain shrink-0" loading="lazy" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="text-[9px] text-ink-dim tabular-nums font-mono">#{relicIndex(r.type)}</span>
                  <p class="text-xs text-ink-primary truncate font-medium">{r.label}</p>
                </div>
                <p class="text-[9px] text-ink-dim leading-tight mt-0.5">
                  {$t('web.players.effigies_rank_hint', { rank: r.rank, max: r.max_rank })}
                </p>
              </div>
            </div>
            <!-- controls: − | clickable progress bar | +  /max -->
            <div class="flex items-center gap-1.5">
              <button type="button"
                class="w-6 h-6 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover disabled:opacity-30 text-sm leading-none shrink-0 flex items-center justify-center transition-fast"
                onclick={() => bump(r.type, -1)} disabled={!supported || saving || val <= 0}
              >−</button>
              <!-- clickable progress bar as the value editor -->
              <div class="relative flex-1 h-7 bg-bg-deep rounded-2 border border-line/40 cursor-pointer overflow-hidden"
                role="slider" aria-label={r.label} aria-valuemin="0" aria-valuemax={r.cumulative_max} aria-valuenow={val}
                onclick={(e) => barClick(r.type, e)}
              >
                <div class="h-full rounded-2 transition-all duration-200 {val >= r.cumulative_max ? 'bg-status-success' : 'bg-accent'}" style="width: {pct}%"></div>
                <span class="absolute inset-0 flex items-center justify-center text-[11px] tabular-nums font-semibold text-white pointer-events-none">{val}</span>
              </div>
              <button type="button"
                class="w-6 h-6 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover disabled:opacity-30 text-sm leading-none shrink-0 flex items-center justify-center transition-fast"
                onclick={() => bump(r.type, 1)} disabled={!supported || saving || val >= r.cumulative_max}
              >+</button>
              <span class="text-[10px] text-ink-dim tabular-nums w-8 text-right shrink-0">/{r.cumulative_max}</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <div class="flex items-center gap-2 pt-2 border-t border-line/20">
      <Button variant="primary" onclick={apply} disabled={!supported || saving}>
        <Icon icon="lucide:check" width={14} class="mr-1" />{$t('web.players.effigies_apply', 'Apply Effigies')}
      </Button>
      <Button variant="ghost" onclick={() => void load()} disabled={loading || saving}>
        <Icon icon="lucide:refresh-cw" width={13} class="mr-1" />{$t('web.common.refresh', 'Refresh')}
      </Button>
    </div>
  </div>
{/if}
