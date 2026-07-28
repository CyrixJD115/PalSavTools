<script lang="ts">
  // Effigies (Lifmunk / relic stat boosts) editor — reusable sub-tab panel.
  // Renders inline in the Player Editor's Effigies tab. Self-loads the current
  // relic state on mount and writes back via setPlayerAbilities.
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
  <div class="p-5 space-y-4 max-w-2xl mx-auto">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:gem" width={16} class="text-accent" />
        <h3 class="text-sm font-semibold text-ink-emphasis">{$t('web.players.edit_effigies', 'Effigies')}</h3>
      </div>
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
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each relics as r (r.type)}
          <label class="block p-3 rounded-4 bg-bg-deep/40 border border-line/30">
            <div class="flex items-baseline justify-between mb-1.5">
              <span class="text-xs font-medium text-ink-primary">{r.label}</span>
              <span class="text-[10px] text-ink-dim">
                {$t('web.players.effigies_rank_hint', { rank: r.rank, max: r.max_rank })} · max {r.cumulative_max}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <input
                class="input flex-1 text-sm"
                type="number"
                min="0"
                max={r.cumulative_max}
                bind:value={relicValues[r.type]}
                disabled={!supported || saving}
              />
              <span class="text-[10px] text-ink-muted tabular-nums w-8 text-right">/{r.cumulative_max}</span>
            </div>
          </label>
        {/each}
      </div>

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
