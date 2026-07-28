<script lang="ts">
  // Player Info panel — summary readout + all quick actions.
  // Renders as the default sub-tab in Player Editor.
  // Matches the app's design language: card groupings, consistent spacing,
  // accent icons, bordered containers, the same section-header pattern
  // used by StatsEditor and other inventory panels.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import type { PlayerDetail } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { uid }: { uid: string } = $props();

  let detail = $state<PlayerDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let renameValue = $state('');
  let editingName = $state(false);
  let levelValue = $state(1);
  let editingLevel = $state(false);
  let saving = $state(false);

  onMount(() => { void load(); });

  async function load() {
    loading = true; error = null;
    try { detail = await api.playerDetail(uid); }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }

  async function act(label: string, fn: () => Promise<unknown>) {
    saving = true;
    try {
      await fn();
      await load();
      editingName = false;
      editingLevel = false;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      saving = false;
    }
  }

  function startRename() {
    renameValue = detail?.name ?? '';
    editingName = true; editingLevel = false;
  }

  function startLevel() {
    levelValue = detail?.level ?? 1;
    editingLevel = true; editingName = false;
  }

  async function handleDelete() {
    if (!confirm($t('web.players.delete_confirm', { name: detail?.name ?? uid }))) return;
    await act('delete', () => api.deletePlayer(uid));
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else if detail}
  <div class="p-5 max-w-xl mx-auto space-y-5">
    <!-- summary card -->
    <div class="bg-bg-surface border border-line/30 rounded-4 p-4 space-y-2.5">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:info" width={12} class="inline mr-1 text-accent" />
        {$t('web.player_editor.player_info', 'Player Info')}
      </p>
      <div class="grid grid-cols-2 gap-x-5 gap-y-2 text-sm">
        <div class="flex items-baseline gap-1.5">
          <Icon icon="lucide:chevrons-up" width={12} class="text-accent shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_level')}</span>
          <span class="tabular-nums text-ink-primary font-medium">{detail.level}</span>
        </div>
        <div class="flex items-baseline gap-1.5">
          <Icon icon="lucide:paw-print" width={12} class="text-accent shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_pals_owned')}</span>
          <span class="tabular-nums text-ink-primary font-medium">{detail.pal_count}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <Icon icon="lucide:building-2" width={12} class="text-accent shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_guild')}</span>
          <Badge tone="accent" class="!text-[10px]">{detail.guild_name ?? '—'}</Badge>
        </div>
        <div class="flex items-baseline gap-1.5">
          <Icon icon="lucide:layers" width={12} class="text-accent shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_guild_level')}</span>
          <span class="tabular-nums">{detail.guild_level}</span>
        </div>
        <div class="col-span-2 flex items-center gap-1.5">
          <Icon icon="lucide:clock" width={12} class="text-ink-dim shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_last_seen')}</span>
          <span class="tabular-nums text-ink-secondary">{detail.last_seen_text ?? 'Unknown'}</span>
        </div>
        <div class="col-span-2 flex items-center gap-1.5">
          <Icon icon="lucide:hash" width={12} class="text-ink-dim shrink-0" />
          <span class="text-ink-muted text-[10px] uppercase tracking-wider">{$t('web.players.detail_uid')}</span>
          <code class="text-[10px] font-mono text-ink-muted truncate select-all">{detail.uid}</code>
        </div>
      </div>
    </div>

    <!-- identity editors card -->
    <div class="bg-bg-surface border border-line/30 rounded-4 p-4 space-y-3">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:user" width={12} class="inline mr-1 text-accent" />
        {$t('web.player_editor.identity', 'Identity')}
      </p>

      <!-- Rename -->
      <div class="flex items-center gap-2">
        <Icon icon="lucide:pencil" width={13} class="text-accent shrink-0" />
        {#if editingName}
          <div class="flex items-center gap-1.5 flex-1">
            <input class="input text-sm flex-1" bind:value={renameValue} disabled={saving} />
            <Button variant="primary" onclick={() => act('rename', () => api.renamePlayer(uid, { name: renameValue.trim() }))} disabled={saving} class="!text-xs !py-1 !px-2.5">{$t('web.common.save')}</Button>
            <Button variant="ghost" onclick={() => editingName = false} class="!text-xs !py-1 !px-2">{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <button type="button" onclick={startRename} disabled={saving} class="flex-1 flex items-center gap-1.5 px-2 py-1 rounded-2 bg-bg-deep border border-line/40 text-ink-primary text-sm hover:bg-bg-hover transition-fast" aria-label={$t('web.common.rename')}>
            <span class="truncate">{detail.name}</span>
            <Icon icon="lucide:pen-line" width={11} class="text-ink-dim shrink-0 ml-auto" />
          </button>
        {/if}
      </div>

      <!-- Set Level -->
      <div class="flex items-center gap-2">
        <Icon icon="lucide:trending-up" width={13} class="text-accent shrink-0" />
        {#if editingLevel}
          <div class="flex items-center gap-1.5">
            <input class="input w-20 text-sm text-center" type="number" min="1" max="80" bind:value={levelValue} disabled={saving} />
            <Button variant="primary" onclick={() => act('level', () => api.setPlayerLevel(uid, { level: levelValue }))} disabled={saving} class="!text-xs !py-1 !px-2.5">{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => editingLevel = false} class="!text-xs !py-1 !px-2">{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <button type="button" onclick={startLevel} disabled={saving} class="flex items-center gap-1.5 px-2 py-1 rounded-2 bg-bg-deep border border-line/40 text-ink-primary text-sm hover:bg-bg-hover transition-fast" aria-label={$t('web.players.set_level')}>
            <Icon icon="lucide:chevrons-up" width={11} class="text-ink-dim" />
            <span class="tabular-nums">{detail.level}</span>
            <Icon icon="lucide:pen-line" width={11} class="text-ink-dim shrink-0 ml-0.5" />
          </button>
        {/if}
      </div>
    </div>

    <!-- actions card -->
    <div class="bg-bg-surface border border-line/30 rounded-4 p-4 space-y-3">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:zap" width={12} class="inline mr-1 text-accent" />
        {$t('web.common.actions')}
      </p>
      <div class="flex flex-wrap gap-2">
        <button type="button" onclick={() => act('reset-ts', () => api.resetPlayerTimestamp(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:clock" width={12} class="text-ink-dim" />
          {$t('web.players.reset_timestamp')}
        </button>
        <button type="button" onclick={() => act('cage', () => api.unlockViewingCage(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:unlock" width={12} class="text-ink-dim" />
          {$t('web.players.unlock_viewing_cage')}
        </button>
        <button type="button" onclick={() => act('unlock-techs', () => api.unlockPlayerTechnologies(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:graduation-cap" width={12} class="text-ink-dim" />
          {$t('web.players.unlock_all_techs')}
        </button>
        <button type="button" onclick={() => act('max-abs', () => api.maxPlayerAbilities({ uids: [uid] }))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:zap" width={12} class="text-ink-dim" />
          {$t('web.players.max_all_abilities')}
        </button>
        <button type="button" onclick={handleDelete} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-status-error/40 text-xs text-status-error hover:bg-status-error/10 hover:border-status-error transition-fast disabled:opacity-40">
          <Icon icon="lucide:trash-2" width={12} />
          {$t('web.players.delete_player')}
        </button>
      </div>
    </div>
  </div>
{/if}
