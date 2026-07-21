<script lang="ts">
  // Player stat readout for the inventory left rail. Renders the six
  // GotStatusPointList ranks + the unused-point pool as compact stat rows.
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import type { PlayerStatsResponse } from '$types/index';

  let { stats }: { stats: PlayerStatsResponse | null } = $props();

  const rows = $derived([
    { key: 'max_hp',    icon: 'lucide:heart',      label: $t('web.inventory.stat_hp',    'Max HP'),     value: stats?.max_hp ?? 0 },
    { key: 'max_sp',    icon: 'lucide:zap',        label: $t('web.inventory.stat_sp',    'Max Stamina'),value: stats?.max_sp ?? 0 },
    { key: 'attack',    icon: 'lucide:sword',      label: $t('web.inventory.stat_atk',   'Attack'),     value: stats?.attack ?? 0 },
    { key: 'weight',    icon: 'lucide:weight',     label: $t('web.inventory.stat_weight','Weight'),     value: stats?.weight ?? 0 },
    { key: 'capture_rate', icon: 'lucide:target',  label: $t('web.inventory.stat_capture','Capture'),   value: stats?.capture_rate ?? 0 },
    { key: 'work_speed',icon: 'lucide:wrench',     label: $t('web.inventory.stat_work',  'Work Speed'), value: stats?.work_speed ?? 0 },
  ]);
</script>

<div class="space-y-1.5">
  <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim mb-1">
    {$t('web.inventory.stats_label', 'Stats')}
  </p>
  {#if !stats}
    <p class="text-xs text-ink-dim italic">{$t('web.inventory.no_stats', 'No stats available.')}</p>
  {:else}
    <div class="grid grid-cols-2 gap-1.5">
      {#each rows as r (r.key)}
        <div class="flex items-center gap-2 px-2 py-1.5 rounded-4 bg-bg-deep/50 border border-line/30">
          <Icon icon={r.icon} width={14} class="text-accent shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="text-[10px] text-ink-muted leading-tight truncate">{r.label}</p>
            <p class="text-sm text-ink-primary font-semibold tabular-nums leading-tight">{r.value}</p>
          </div>
        </div>
      {/each}
    </div>
    {#if stats.unused_stat_points > 0}
      <div class="flex items-center gap-2 px-2 py-1.5 rounded-4 bg-status-warning/10 border border-status-warning/30">
        <Icon icon="lucide:sparkles" width={14} class="text-status-warning shrink-0" />
        <p class="text-xs text-status-warning font-medium">
          {stats.unused_stat_points} {$t('web.inventory.unused_points', 'unused points')}
        </p>
      </div>
    {/if}
  {/if}
</div>
