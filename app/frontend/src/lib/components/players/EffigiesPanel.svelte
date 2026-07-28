<script lang="ts">
  // Effigies editor — compact row-per-relic layout.
  // Matches StatsEditor's dense single-column style for efficient editing.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import Spinner from '$components/ui/Spinner.svelte';
  import Button from '$components/ui/Button.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import type { RelicEntry } from '$types/index';

  let { uid }: { uid: string } = $props();

  let relics = $state<RelicEntry[]>([]);
  let relicValues = $state<Record<string, number>>({});
  let supported = $state(true);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saving = $state(false);

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
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else}
  <div class="p-5 max-w-2xl mx-auto space-y-4">
    <!-- header -->
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:gem" width={12} class="inline mr-1.5 text-accent" />
        {$t('web.players.edit_effigies', 'Effigies')}
      </p>
      <Button variant="ghost" onclick={setAllToMax} disabled={!supported || saving} class="!text-xs">
        <Icon icon="lucide:zap" width={13} class="mr-1" />
        {$t('web.players.max_all_abilities', 'Max All')}
      </Button>
    </div>

    {#if !supported}
      <p class="text-xs text-status-warning">{$t('web.players.effigies_unsupported')}</p>
    {/if}

    {#if relics.length === 0}
      <EmptyState icon="lucide:gem" title={$t('web.players.edit_effigies', 'Effigies')} class="py-8">
        <p class="text-xs">{$t('web.players.effigies_unsupported')}</p>
      </EmptyState>
    {:else}
      <!-- relic rows — dense single-column, like StatsEditor's stat rows -->
      <div class="space-y-1">
        {#each relics as r (r.type)}
          <div class="flex items-center gap-2 py-1.5 px-1 rounded-2 hover:bg-bg-hover/40 transition-fast group">
            <Icon icon="lucide:gem" width={12} class="text-accent shrink-0" />
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

      <!-- footer actions -->
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
    {/if}
  </div>
{/if}
