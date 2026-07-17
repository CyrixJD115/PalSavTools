<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import type { PlayerDetail, PlayerStatsResponse, PlayerTechPointsResponse } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { uid, name: playerName, onclose, onupdated }: {
    uid: string;
    name: string;
    onclose: () => void;
    onupdated: () => void;
  } = $props();

  let detail = $state<PlayerDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);
  let renameValue = $state('');
  let editingName = $state(false);
  let levelValue = $state(1);
  let editingLevel = $state(false);
  let techPoints = $state(0);
  let bossTechPoints = $state(0);
  let editingTech = $state(false);
  let stats = $state({ max_hp: 0, max_sp: 0, attack: 0, weight: 0, capture_rate: 0, work_speed: 0, unused_stat_points: 0 });
  let editingStats = $state(false);

  async function load() {
    loading = true; error = null;
    try { detail = await api.playerDetail(uid); }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(load);

  async function doAction(name: string, fn: () => Promise<unknown>) {
    actionError = null;
    actionLoading = name;
    try {
      await fn();
      if (name !== 'close') await load();
      if (name === 'delete') onupdated();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function doRename() {
    if (!renameValue.trim()) return;
    await doAction('rename', () => api.renamePlayer(uid, { name: renameValue.trim() }));
    editingName = false;
  }

  async function doSetLevel() {
    await doAction('set-level', () => api.setPlayerLevel(uid, { level: levelValue }));
    editingLevel = false;
  }

  async function doTechPoints() {
    await doAction('tech-points', () => api.setPlayerTechPoints(uid, { tech_points: techPoints, boss_tech_points: bossTechPoints }));
    editingTech = false;
  }

  async function doStats() {
    const body: Record<string, number> = {};
    // Use !== undefined so 0 values are properly sent
    if (stats.max_hp !== undefined) body.max_hp = stats.max_hp;
    if (stats.max_sp !== undefined) body.max_sp = stats.max_sp;
    if (stats.attack !== undefined) body.attack = stats.attack;
    if (stats.weight !== undefined) body.weight = stats.weight;
    if (stats.capture_rate !== undefined) body.capture_rate = stats.capture_rate;
    if (stats.work_speed !== undefined) body.work_speed = stats.work_speed;
    body.unused_stat_points = stats.unused_stat_points;
    await doAction('stats', () => api.setPlayerStats(uid, body));
    editingStats = false;
  }

  function startRename() { renameValue = detail?.name ?? ''; editingName = true; }

  function startLevel() { levelValue = detail?.level ?? 1; editingLevel = true; }

  async function startTech() {
    // Fetch current values from the backend instead of hardcoding 0
    try {
      const tp = await api.playerTechPoints(uid);
      techPoints = tp.tech_points;
      bossTechPoints = tp.boss_tech_points;
    } catch {
      techPoints = 0;
      bossTechPoints = 0;
    }
    editingTech = true;
  }

  async function startStats() {
    // Fetch current values from the backend instead of hardcoding 0
    try {
      const s = await api.playerStats(uid);
      stats = { max_hp: s.max_hp, max_sp: s.max_sp, attack: s.attack, weight: s.weight, capture_rate: s.capture_rate, work_speed: s.work_speed, unused_stat_points: s.unused_stat_points };
    } catch {
      stats = { max_hp: 0, max_sp: 0, attack: 0, weight: 0, capture_rate: 0, work_speed: 0, unused_stat_points: 0 };
    }
    editingStats = true;
  }

  function handleDelete() {
    if (!confirm($t('web.players.delete_confirm', { name: detail?.name ?? uid }))) return;
    doAction('delete', () => api.deletePlayer(uid));
  }

  function handleViewingCage() {
    doAction('viewing-cage', () => api.unlockViewingCage(uid));
  }

  function handleResetTimestamp() {
    doAction('reset-timestamp', () => api.resetPlayerTimestamp(uid));
  }

  function handleUnlockTechs() {
    doAction('unlock-techs', () => api.unlockPlayerTechnologies(uid));
  }

  async function handleMaxAbilities() {
    actionError = null;
    actionLoading = 'max-abilities';
    try {
      const resp = await api.maxPlayerAbilities({ uids: [uid] }) as unknown as { status: string; processed: number; failed_uids?: string[] };
      if (resp.status === 'failed') {
        actionError = $t('web.players.max_abilities_missing');
      } else if (resp.failed_uids?.length) {
        actionError = $t('web.players.max_abilities_partial', { processed: resp.processed, failed: resp.failed_uids.length });
      }
      if (resp.status !== 'failed') await load();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} role="dialog" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto animate-scale-in"
    transition:scale={{ start: 0.95, duration: 150 }}
    role="presentation"
    onclick={(e: MouseEvent) => e.stopPropagation()}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:user" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">{detail?.name ?? playerName}</h2>
        {#if detail?.is_leader}<Badge tone="accent">{$t('web.players.leader_badge')}</Badge>{/if}
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast" onclick={onclose}>
        <Icon icon="lucide:x" width={20} />
      </button>
    </div>

    {#if loading}
      <div class="flex justify-center py-12"><Spinner size={24} /></div>
    {:else if error}
      <p class="text-sm text-status-error p-4">{error}</p>
    {:else if detail}
      <!-- stats row -->
      <div class="grid grid-cols-2 gap-4 p-4 border-b border-line/20 text-sm">
        <div><span class="text-ink-muted">{$t('web.players.detail_level')}</span> <span class="tabular-nums text-ink-primary font-medium">{detail.level}</span></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_pals_owned')}</span> <span class="tabular-nums text-ink-primary font-medium">{detail.pal_count}</span></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_guild')}</span> <Badge tone="accent">{detail.guild_name ?? '—'}</Badge></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_guild_level')}</span> <span class="tabular-nums">{detail.guild_level}</span></div>
        <div class="col-span-2"><span class="text-ink-muted">{$t('web.players.detail_last_seen')}</span> <span class="tabular-nums">{detail.last_seen_text ?? 'Unknown'}</span></div>
        <div class="col-span-2">
          <span class="text-ink-muted">{$t('web.players.detail_uid')}</span>
          <code class="text-xs font-mono text-ink-muted ml-1">{detail.uid}</code>
        </div>
      </div>

      <!-- actions -->
      <div class="p-4 space-y-3">
        {#if actionError}
          <p class="text-xs text-status-error">{actionError}</p>
        {/if}

        <p class="text-xs uppercase tracking-wider text-ink-muted font-medium">{$t('web.common.actions')}</p>

        <!-- Rename -->
        {#if editingName}
          <div class="flex gap-2 items-center">
            <input class="input flex-1 text-sm" bind:value={renameValue} placeholder={$t('web.players.rename_label')} />
            <Button variant="primary" onclick={doRename} disabled={actionLoading !== null}>{$t('web.common.save')}</Button>
            <Button variant="ghost" onclick={() => editingName = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startRename} disabled={actionLoading !== null}>
            <Icon icon="lucide:pencil" width={14} class="mr-1" /> {$t('web.common.rename')}
          </Button>
        {/if}

        <!-- Set Level -->
        {#if editingLevel}
          <div class="flex gap-2 items-center">
            <input class="input w-24 text-sm" type="number" min="1" max="80" bind:value={levelValue} />
            <Button variant="primary" onclick={doSetLevel} disabled={actionLoading !== null}>{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => editingLevel = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startLevel} disabled={actionLoading !== null}>
            <Icon icon="lucide:trending-up" width={14} class="mr-1" /> {$t('web.players.set_level')}
          </Button>
        {/if}

        <!-- Tech Points -->
        {#if editingTech}
          <div class="flex gap-2 items-center flex-wrap">
            <label class="text-xs text-ink-muted">{$t('web.players.tech')}
              <input class="input w-20 text-sm ml-1" type="number" min="0" bind:value={techPoints} />
            </label>
            <label class="text-xs text-ink-muted">{$t('web.players.ancient')}
              <input class="input w-20 text-sm ml-1" type="number" min="0" bind:value={bossTechPoints} />
            </label>
            <Button variant="primary" onclick={doTechPoints} disabled={actionLoading !== null}>{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => editingTech = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startTech} disabled={actionLoading !== null}>
            <Icon icon="lucide:flask-conical" width={14} class="mr-1" /> {$t('web.players.edit_tech')}
          </Button>
        {/if}

        <!-- Stats -->
        {#if editingStats}
          <div class="grid grid-cols-3 gap-2 text-sm">
            {#each [{key:'max_hp',labelKey:'web.players.max_hp'},{key:'max_sp',labelKey:'web.players.max_sp'},{key:'attack',labelKey:'web.players.attack'},{key:'weight',labelKey:'web.players.weight'},{key:'capture_rate',labelKey:'web.players.capture'},{key:'work_speed',labelKey:'web.players.work_spd'}] as stat}
              <label class="text-xs text-ink-muted block">
                {$t(stat.labelKey)}
                <input class="input w-full text-sm mt-0.5" type="number" min="0" bind:value={stats[stat.key as keyof typeof stats]} />
              </label>
            {/each}
            <div class="col-span-3">
              <label class="text-xs text-ink-muted">
                {$t('web.players.unused_stat_points')}
                <input class="input w-24 text-sm mt-0.5" type="number" min="0" bind:value={stats.unused_stat_points} />
              </label>
            </div>
          </div>
          <div class="flex gap-2 mt-2">
            <Button variant="primary" onclick={doStats} disabled={actionLoading !== null}>{$t('web.players.apply_stats')}</Button>
            <Button variant="ghost" onclick={() => editingStats = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startStats} disabled={actionLoading !== null}>
            <Icon icon="lucide:activity" width={14} class="mr-1" /> {$t('web.players.edit_stats')}
          </Button>
        {/if}

        <div class="border-t border-line/20 pt-3 flex flex-wrap gap-2">
          <Button variant="secondary" onclick={handleResetTimestamp} disabled={actionLoading !== null}>
            <Icon icon="lucide:clock" width={14} class="mr-1" /> {$t('web.players.reset_timestamp')}
          </Button>
          <Button variant="secondary" onclick={handleViewingCage} disabled={actionLoading !== null}>
            <Icon icon="lucide:unlock" width={14} class="mr-1" /> {$t('web.players.unlock_viewing_cage')}
          </Button>
          <Button variant="secondary" onclick={handleUnlockTechs} disabled={actionLoading !== null}>
            <Icon icon="lucide:graduation-cap" width={14} class="mr-1" /> {$t('web.players.unlock_all_techs')}
          </Button>
          <Button variant="secondary" onclick={handleMaxAbilities} disabled={actionLoading !== null}>
            <Icon icon="lucide:zap" width={14} class="mr-1" /> {$t('web.players.max_all_abilities')}
          </Button>
        </div>

        <!-- Delete (danger) -->
        <div class="border-t border-line/20 pt-3">
          <Button variant="danger" onclick={handleDelete} disabled={actionLoading !== null}>
            <Icon icon="lucide:trash-2" width={14} class="mr-1" /> {$t('web.players.delete_player')}
          </Button>
        </div>
      </div>
    {/if}
  </div>
</div>
