<script lang="ts">
  // Player detail popup — slimmed down for quick actions only.
  //
  // Heavy editing (Stats, Tech, Effigies, Missions, Tech Tree, Pals, Delete,
  // Max Abilities, Unlock All Techs) now lives in the Player Editor page
  // (/player-editor). This popup covers:
  //   - Read-only summary (level, guild, last seen, UID)
  //   - Quick inlines: Rename, Set Level
  //   - One-click actions: Reset Timestamp, Unlock Viewing Cage
  //   - "Open in Player Editor" deep-link button
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import type { PlayerDetail } from '$types/index';
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

  // inline editors
  let renameValue = $state('');
  let editingName = $state(false);
  let levelValue = $state(1);
  let editingLevel = $state(false);

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
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  function startRename() {
    renameValue = detail?.name ?? '';
    editingName = true;
    editingLevel = false;
  }

  function startLevel() {
    levelValue = detail?.level ?? 1;
    editingLevel = true;
    editingName = false;
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

  function openPlayerEditor() {
    goto('/player-editor?uid=' + uid);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} role="dialog" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-xl w-full mx-5 max-h-[85vh] overflow-y-auto animate-scale-in"
    transition:fade={{ duration: 120 }}
    role="presentation"
    onclick={(e: MouseEvent) => e.stopPropagation()}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-5 border-b border-line/20">
      <div class="flex items-center gap-2.5 min-w-0">
        <Icon icon="lucide:user" width={20} class="text-accent shrink-0" />
        <h2 class="text-lg font-bold heading-gradient truncate">{detail?.name ?? playerName}</h2>
        {#if detail?.is_leader}<Badge tone="accent">{$t('web.players.leader_badge')}</Badge>{/if}
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast shrink-0" onclick={onclose}>
        <Icon icon="lucide:x" width={22} />
      </button>
    </div>

    {#if loading}
      <div class="flex justify-center py-16"><Spinner size={24} /></div>
    {:else if error}
      <p class="text-sm text-status-error p-5">{error}</p>
    {:else if detail}
      <!-- summary stats grid -->
      <div class="grid grid-cols-2 gap-4 p-5 border-b border-line/20 text-sm">
        <div><span class="text-ink-muted">{$t('web.players.detail_level')}</span> <span class="tabular-nums text-ink-primary font-medium ml-1">{detail.level}</span></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_pals_owned')}</span> <span class="tabular-nums text-ink-primary font-medium ml-1">{detail.pal_count}</span></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_guild')}</span> <span class="ml-1"><Badge tone="accent">{detail.guild_name ?? '—'}</Badge></span></div>
        <div><span class="text-ink-muted">{$t('web.players.detail_guild_level')}</span> <span class="tabular-nums ml-1">{detail.guild_level}</span></div>
        <div class="col-span-2"><span class="text-ink-muted">{$t('web.players.detail_last_seen')}</span> <span class="tabular-nums ml-1">{detail.last_seen_text ?? 'Unknown'}</span></div>
        <div class="col-span-2">
          <span class="text-ink-muted">{$t('web.players.detail_uid')}</span>
          <code class="text-xs font-mono text-ink-muted ml-2 break-all">{detail.uid}</code>
        </div>
      </div>

      <!-- quick actions -->
      <div class="p-5 space-y-4">
        {#if actionError}
          <p class="text-xs text-status-error">{actionError}</p>
        {/if}

        <p class="text-xs uppercase tracking-wider text-ink-muted font-semibold">{$t('web.common.actions')}</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Rename -->
          {#if editingName}
            <div class="sm:col-span-2 flex gap-2 items-center">
              <input class="input flex-1 text-sm" bind:value={renameValue} placeholder={$t('web.players.rename_label')} />
              <Button variant="primary" onclick={doRename} disabled={actionLoading !== null}>{$t('web.common.save')}</Button>
              <Button variant="ghost" onclick={() => editingName = false}>{$t('web.common.cancel')}</Button>
            </div>
          {:else}
            <Button variant="secondary" onclick={startRename} disabled={actionLoading !== null} class="!justify-start">
              <Icon icon="lucide:pencil" width={14} class="mr-1.5 shrink-0" />
              <span>{$t('web.common.rename')}</span>
            </Button>
          {/if}

          <!-- Set Level -->
          {#if editingLevel}
            <div class="sm:col-span-2 flex gap-2 items-center">
              <input class="input w-24 text-sm" type="number" min="1" max="80" bind:value={levelValue} />
              <Button variant="primary" onclick={doSetLevel} disabled={actionLoading !== null}>{$t('web.common.set')}</Button>
              <Button variant="ghost" onclick={() => editingLevel = false}>{$t('web.common.cancel')}</Button>
            </div>
          {:else}
            <Button variant="secondary" onclick={startLevel} disabled={actionLoading !== null} class="!justify-start">
              <Icon icon="lucide:trending-up" width={14} class="mr-1.5 shrink-0" />
              <span>{$t('web.players.set_level')}</span>
            </Button>
          {/if}
        </div>

        <!-- one-click utility actions -->
        <div class="flex flex-wrap gap-2 pt-2 border-t border-line/20">
          <Button variant="secondary" onclick={() => doAction('reset-ts', () => api.resetPlayerTimestamp(uid))} disabled={actionLoading !== null} class="!text-xs">
            <Icon icon="lucide:clock" width={13} class="mr-1" /> {$t('web.players.reset_timestamp')}
          </Button>
          <Button variant="secondary" onclick={() => doAction('cage', () => api.unlockViewingCage(uid))} disabled={actionLoading !== null} class="!text-xs">
            <Icon icon="lucide:unlock" width={13} class="mr-1" /> {$t('web.players.unlock_viewing_cage')}
          </Button>
        </div>
      </div>

      <!-- Open in Player Editor -->
      <div class="px-5 pb-5">
        <Button variant="primary" onclick={openPlayerEditor} class="w-full !text-sm !py-2.5">
          <Icon icon="lucide:external-link" width={15} class="mr-1.5" />
          {$t('web.players.open_player_editor', 'Open in Player Editor \u2192')}
        </Button>
      </div>
    {/if}
  </div>
</div>
