<script lang="ts">
  // Editable player stat panel — replaces the read-only StatsPanel on the
  // inventory page. Each row shows the in-game computed value (e.g. HP 5500 =
  // 500 base + 50 points × 100) plus a `-` / number input / `+` control to
  // edit the raw rank value. Level + tech points rows are folded in for a
  // unified editor (mirrors PST's StatsPanelWidget).
  //
  // Writes are debounced 400ms; each stat change fires the corresponding API
  // call. "Max All" / "Reset" buttons call the convenience endpoints.
  import Icon from '@iconify/svelte';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import { api } from '$lib/api/client';
  import type { PlayerStatsResponse, PlayerTechPointsResponse } from '$types/index';

  let {
    uid,
    stats,
    techPoints,
    level,
  }: {
    uid: string;
    stats: PlayerStatsResponse | null;
    techPoints: PlayerTechPointsResponse | null;
    level: number;
  } = $props();

  // Local editable mirrors of the prop values — init from props, then track
  // user edits. We sync from props when the player changes (via $effect).
  let local = $state<Record<string, number>>({});
  let localTech = $state({ tech_points: 0, boss_tech_points: 0 });
  let localLevel = $state(1);
  let saving = $state<string | null>(null);   // which field is saving (null = idle)
  let error = $state<string | null>(null);

  // Stat definitions: key, icon, label, base + per-point multiplier (matches
  // PST's HERO_STATS formulas so the computed value matches the game).
  type StatDef = { key: keyof PlayerStatsResponse; icon: string; labelKey: string; fallback: string; base: number; mult: number };
  const STAT_DEFS: StatDef[] = [
    { key: 'max_hp',    icon: 'lucide:heart',      labelKey: 'web.inventory.stat_hp',     fallback: 'Max HP',     base: 500, mult: 100 },
    { key: 'max_sp',    icon: 'lucide:zap',        labelKey: 'web.inventory.stat_sp',     fallback: 'Max Stamina',base: 100, mult: 10 },
    { key: 'attack',    icon: 'lucide:sword',      labelKey: 'web.inventory.stat_atk',    fallback: 'Attack',     base: 100, mult: 2 },
    { key: 'weight',    icon: 'lucide:weight',     labelKey: 'web.inventory.stat_weight', fallback: 'Weight',     base: 300, mult: 50 },
    { key: 'capture_rate', icon: 'lucide:target',  labelKey: 'web.inventory.stat_capture',fallback: 'Capture',    base: 0,   mult: 1 },
    { key: 'work_speed',icon: 'lucide:wrench',     labelKey: 'web.inventory.stat_work',   fallback: 'Work Speed', base: 100, mult: 50 },
  ];

  // Sync local state when the player (or fresh data) changes.
  $effect(() => {
    if (stats) {
      local = {
        max_hp: stats.max_hp, max_sp: stats.max_sp, attack: stats.attack,
        weight: stats.weight, capture_rate: stats.capture_rate, work_speed: stats.work_speed,
        unused_stat_points: stats.unused_stat_points,
      };
    }
    if (techPoints) {
      localTech = { tech_points: techPoints.tech_points, boss_tech_points: techPoints.boss_tech_points };
    }
    localLevel = level || 1;
  });

  function computed(d: StatDef): number {
    return d.base + (local[d.key] ?? 0) * d.mult;
  }

  // Debounced write per-stat. Each stat change schedules a single PUT /stats
  // with just that field; rapid +/- clicks coalesce into one request.
  const debouncers: Record<string, ReturnType<typeof setTimeout>> = {};
  function scheduleStat(key: string) {
    clearTimeout(debouncers[key]);
    debouncers[key] = setTimeout(() => void writeStat(key), 400);
  }

  async function writeStat(key: string) {
    if (!uid) return;
    saving = key; error = null;
    try {
      const body: Record<string, number> = { [key]: local[key] };
      await api.setPlayerStats(uid, body);
      toast.success($t('web.inventory.stats_saved', 'Stat saved.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = null;
    }
  }

  async function writeTech() {
    if (!uid) return;
    saving = 'tech'; error = null;
    try {
      await api.setPlayerTechPoints(uid, localTech);
      toast.success($t('web.inventory.tech_points_saved', 'Tech points saved.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = null;
    }
  }

  async function writeLevel() {
    if (!uid) return;
    const v = Math.max(1, Math.min(80, localLevel));
    if (v === level) return;
    saving = 'level'; error = null;
    try {
      await api.setPlayerLevel(uid, { level: v });
      localLevel = v;
      toast.success($t('web.inventory.level_saved', 'Level saved.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = null;
    }
  }

  function bumpStat(key: keyof PlayerStatsResponse, delta: number) {
    const cur = local[key] ?? 0;
    const next = Math.max(0, Math.min(100, cur + delta));
    if (next === cur) return;
    local[key] = next;
    scheduleStat(key);
  }

  function bumpLevel(delta: number) {
    localLevel = Math.max(1, Math.min(80, localLevel + delta));
    clearTimeout(debouncers['level']);
    debouncers['level'] = setTimeout(() => void writeLevel(), 400);
  }

  function bumpTech(key: 'tech_points' | 'boss_tech_points', delta: number) {
    localTech[key] = Math.max(0, Math.min(9999999, (localTech[key] ?? 0) + delta));
    clearTimeout(debouncers['tech']);
    debouncers['tech'] = setTimeout(() => void writeTech(), 400);
  }

  async function maxAll() {
    if (!uid) return;
    saving = 'max'; error = null;
    try {
      await api.maxPlayerStats(uid);
      // Refresh local from the response — re-read via the API to get canonical values.
      const fresh = await api.playerStats(uid);
      local = {
        max_hp: fresh.max_hp, max_sp: fresh.max_sp, attack: fresh.attack,
        weight: fresh.weight, capture_rate: fresh.capture_rate, work_speed: fresh.work_speed,
        unused_stat_points: fresh.unused_stat_points,
      };
      toast.success($t('web.inventory.max_all_done', 'All stats maxed.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = null;
    }
  }

  async function resetAll() {
    if (!uid) return;
    if (!confirm($t('web.inventory.reset_confirm', 'Reset all stats to zero?'))) return;
    saving = 'reset'; error = null;
    try {
      await api.resetPlayerStats(uid);
      const fresh = await api.playerStats(uid);
      local = {
        max_hp: fresh.max_hp, max_sp: fresh.max_sp, attack: fresh.attack,
        weight: fresh.weight, capture_rate: fresh.capture_rate, work_speed: fresh.work_speed,
        unused_stat_points: fresh.unused_stat_points,
      };
      toast.success($t('web.inventory.reset_done', 'Stats reset.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = null;
    }
  }
</script>

<div class="space-y-2.5">
  <div class="flex items-center justify-between">
    <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
      {$t('web.inventory.stats_label', 'Stats')}
    </p>
    {#if saving}
      <span class="text-[10px] text-ink-muted flex items-center gap-1">
        <Icon icon="eos-icons:loading" width={11} /> {$t('web.common.saving', 'Saving…')}
      </span>
    {/if}
  </div>

  {#if !stats}
    <p class="text-xs text-ink-dim italic">{$t('web.inventory.no_stats', 'No stats available.')}</p>
  {:else}
    <!-- Six core stats -->
    <div class="space-y-1">
      {#each STAT_DEFS as d (d.key)}
        <div class="flex items-center gap-1.5">
          <Icon icon={d.icon} width={13} class="text-accent shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-[9px] text-ink-muted leading-none truncate">{$t(d.labelKey, d.fallback)}</p>
            <p class="text-[10px] text-ink-dim tabular-nums leading-tight">
              {$t('web.inventory.computed_value', { value: computed(d).toLocaleString() })}
            </p>
          </div>
          <button
            type="button"
            class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
            onclick={() => bumpStat(d.key, -1)}
            aria-label="Decrease"
          >−</button>
          <input
            class="stat-input w-12 bg-bg-deep border border-line/40 rounded-2 px-1 py-0.5 text-sm text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent"
            type="number"
            min="0"
            max="100"
            value={local[d.key] ?? 0}
            oninput={(e) => { local[d.key] = Math.max(0, Math.min(100, Number((e.currentTarget as HTMLInputElement).value) || 0)); scheduleStat(d.key); }}
          >
          <button
            type="button"
            class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
            onclick={() => bumpStat(d.key, +1)}
            aria-label="Increase"
          >+</button>
        </div>
      {/each}
    </div>

    {#if (local.unused_stat_points ?? 0) > 0}
      <div class="flex items-center gap-2 px-2 py-1 rounded-4 bg-status-warning/10 border border-status-warning/30">
        <Icon icon="lucide:sparkles" width={12} class="text-status-warning shrink-0" />
        <p class="text-[10px] text-status-warning font-medium">
          {local.unused_stat_points} {$t('web.inventory.unused_points', 'unused points')}
        </p>
      </div>
    {/if}

    <!-- Level -->
    <div class="pt-2 border-t border-line/20 space-y-1.5">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        {$t('web.inventory.level_label', 'Level')}
      </p>
      <div class="flex items-center gap-1.5">
        <Icon icon="lucide:chevrons-up" width={13} class="text-accent shrink-0" />
        <button
          type="button"
          class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
          onclick={() => bumpLevel(-1)} aria-label="Decrease level"
        >−</button>
        <input
          class="stat-input w-14 bg-bg-deep border border-line/40 rounded-2 px-1 py-0.5 text-sm text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent"
          type="number" min="1" max="80"
          value={localLevel}
          oninput={(e) => { localLevel = Math.max(1, Math.min(80, Number((e.currentTarget as HTMLInputElement).value) || 1)); clearTimeout(debouncers['level']); debouncers['level'] = setTimeout(() => void writeLevel(), 400); }}
        >
        <button
          type="button"
          class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
          onclick={() => bumpLevel(+1)} aria-label="Increase level"
        >+</button>
        <span class="text-[9px] text-ink-muted ml-1">1–80</span>
      </div>
    </div>

    <!-- Tech points -->
    {#if techPoints}
      <div class="pt-2 border-t border-line/20 space-y-1.5">
        <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
          {$t('web.inventory.tech_points_label', 'Tech Points')}
        </p>
        <div class="space-y-1">
          <div class="flex items-center gap-1.5">
            <Icon icon="lucide:flask-conical" width={12} class="text-accent shrink-0" />
            <span class="text-[10px] text-ink-muted flex-1">{$t('web.inventory.tech_points_normal', 'Technology')}</span>
            <button
              type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
              onclick={() => bumpTech('tech_points', -10)} aria-label="Decrease tech"
            >−</button>
            <input
              class="stat-input w-20 bg-bg-deep border border-line/40 rounded-2 px-1 py-0.5 text-sm text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent"
              type="number" min="0" max="9999999"
              value={localTech.tech_points}
              oninput={(e) => { localTech.tech_points = Math.max(0, Math.min(9999999, Number((e.currentTarget as HTMLInputElement).value) || 0)); clearTimeout(debouncers['tech']); debouncers['tech'] = setTimeout(() => void writeTech(), 400); }}
            >
            <button
              type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
              onclick={() => bumpTech('tech_points', +10)} aria-label="Increase tech"
            >+</button>
          </div>
          <div class="flex items-center gap-1.5">
            <Icon icon="lucide:atom" width={12} class="text-amber-400 shrink-0" />
            <span class="text-[10px] text-ink-muted flex-1">{$t('web.inventory.tech_points_boss', 'Ancient')}</span>
            <button
              type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
              onclick={() => bumpTech('boss_tech_points', -1)} aria-label="Decrease boss tech"
            >−</button>
            <input
              class="stat-input w-20 bg-bg-deep border border-line/40 rounded-2 px-1 py-0.5 text-sm text-center text-ink-primary tabular-nums focus:outline-none focus:border-accent"
              type="number" min="0" max="9999999"
              value={localTech.boss_tech_points}
              oninput={(e) => { localTech.boss_tech_points = Math.max(0, Math.min(9999999, Number((e.currentTarget as HTMLInputElement).value) || 0)); clearTimeout(debouncers['tech']); debouncers['tech'] = setTimeout(() => void writeTech(), 400); }}
            >
            <button
              type="button"
              class="w-5 h-5 rounded-2 bg-bg-deep border border-line/40 text-ink-secondary hover:bg-bg-hover text-xs leading-none flex items-center justify-center transition-fast"
              onclick={() => bumpTech('boss_tech_points', +1)} aria-label="Increase boss tech"
            >+</button>
          </div>
        </div>
      </div>
    {/if}

    {#if error}
      <p class="text-[10px] text-status-error">{error}</p>
    {/if}

    <!-- Action buttons -->
    <div class="flex gap-1.5 pt-2 border-t border-line/20">
      <Button variant="primary" onclick={maxAll} disabled={saving !== null} class="!py-1 !px-2 !text-[11px] flex-1">
        <Icon icon="lucide:chevrons-up" width={11} class="mr-0.5" />
        {$t('web.inventory.max_all', 'Max All')}
      </Button>
      <Button variant="ghost" onclick={resetAll} disabled={saving !== null} class="!py-1 !px-2 !text-[11px] flex-1">
        <Icon icon="lucide:rotate-ccw" width={11} class="mr-0.5" />
        {$t('web.inventory.reset', 'Reset')}
      </Button>
    </div>
  {/if}
</div>

<style>
  /* Hide browser-native number-input spinner arrows — redundant with -/+ buttons */
  .stat-input::-webkit-outer-spin-button,
  .stat-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .stat-input[type="number"] {
    -moz-appearance: textfield;
    appearance: textfield;
  }
</style>
