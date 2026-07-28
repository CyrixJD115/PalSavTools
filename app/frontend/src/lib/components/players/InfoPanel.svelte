<script lang="ts">
  // Player Info panel — flat layout, no nested cards.
  // Summary readout + identity editors + one-click actions, separated by
  // thin dividers. Matches the app's dense, clean information style.
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
  <div class="p-5 max-w-xl mx-auto">
    <!-- summary grid — no card, just clean data -->
    <div class="grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:chevrons-up" width={13} class="text-accent shrink-0" />
        <div>
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_level')}</p>
          <p class="tabular-nums text-ink-primary font-medium leading-tight">{detail.level}</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Icon icon="lucide:paw-print" width={13} class="text-accent shrink-0" />
        <div>
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_pals_owned')}</p>
          <p class="tabular-nums text-ink-primary font-medium leading-tight">{detail.pal_count}</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Icon icon="lucide:building-2" width={13} class="text-accent shrink-0" />
        <div>
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_guild')}</p>
          <Badge tone="accent" class="!text-[10px]">{detail.guild_name ?? '—'}</Badge>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Icon icon="lucide:layers" width={13} class="text-accent shrink-0" />
        <div>
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_guild_level')}</p>
          <p class="tabular-nums text-ink-primary font-medium leading-tight">{detail.guild_level}</p>
        </div>
      </div>
      <div class="col-span-2 flex items-center gap-2">
        <Icon icon="lucide:clock" width={13} class="text-ink-dim shrink-0" />
        <div>
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_last_seen')}</p>
          <p class="tabular-nums text-ink-secondary leading-tight">{detail.last_seen_text ?? 'Unknown'}</p>
        </div>
      </div>
      <div class="col-span-2 flex items-center gap-2 pt-1">
        <Icon icon="lucide:hash" width={13} class="text-ink-dim shrink-0" />
        <div class="min-w-0">
          <p class="text-[9px] text-ink-dim uppercase tracking-wider leading-tight">{$t('web.players.detail_uid')}</p>
          <code class="text-[10px] font-mono text-ink-muted truncate block select-all">{detail.uid}</code>
        </div>
      </div>
    </div>

    <!-- divider -->
    <div class="border-t border-line/20 my-5"></div>

    <!-- identity editors -->
    <div class="space-y-3 mb-0">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:user" width={12} class="inline mr-1.5 text-accent" />{$t('web.player_editor.identity', 'Identity')}
      </p>

      <div class="flex items-center gap-2">
        <span class="w-16 text-[10px] text-ink-dim uppercase tracking-wider shrink-0">{$t('web.common.name', 'Name')}</span>
        {#if editingName}
          <div class="flex items-center gap-1.5 flex-1">
            <input class="input text-sm flex-1" bind:value={renameValue} disabled={saving} />
            <Button variant="primary" onclick={() => act('rename', () => api.renamePlayer(uid, { name: renameValue.trim() }))} disabled={saving} class="!text-xs !py-1 !px-2.5">{$t('web.common.save')}</Button>
            <Button variant="ghost" onclick={() => editingName = false} class="!text-xs !py-1 !px-2">{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <div class="flex items-center gap-1.5">
            <span class="text-sm text-ink-primary">{detail.name}</span>
            <button type="button" onclick={startRename} disabled={saving} class="text-ink-dim hover:text-accent transition-fast" aria-label={$t('web.common.rename')}>
              <Icon icon="lucide:pen-line" width={12} />
            </button>
          </div>
        {/if}
      </div>

      <div class="flex items-center gap-2">
        <span class="w-16 text-[10px] text-ink-dim uppercase tracking-wider shrink-0">{$t('web.players.set_level', 'Level')}</span>
        {#if editingLevel}
          <div class="flex items-center gap-1.5">
            <input class="input w-20 text-sm text-center" type="number" min="1" max="80" bind:value={levelValue} disabled={saving} />
            <Button variant="primary" onclick={() => act('level', () => api.setPlayerLevel(uid, { level: levelValue }))} disabled={saving} class="!text-xs !py-1 !px-2.5">{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => editingLevel = false} class="!text-xs !py-1 !px-2">{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <div class="flex items-center gap-1.5">
            <span class="text-sm tabular-nums text-ink-primary">{detail.level}</span>
            <button type="button" onclick={startLevel} disabled={saving} class="text-ink-dim hover:text-accent transition-fast" aria-label={$t('web.players.set_level')}>
              <Icon icon="lucide:pen-line" width={12} />
            </button>
          </div>
        {/if}
      </div>
    </div>

    <!-- divider -->
    <div class="border-t border-line/20 my-5"></div>

    <!-- actions -->
    <div class="space-y-3">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
        <Icon icon="lucide:zap" width={12} class="inline mr-1.5 text-accent" />{$t('web.common.actions')}
      </p>

      <div class="flex flex-wrap gap-x-2 gap-y-2.5">
        <button type="button" onclick={() => act('reset-ts', () => api.resetPlayerTimestamp(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:clock" width={13} class="text-ink-dim" />
          {$t('web.players.reset_timestamp')}
        </button>
        <button type="button" onclick={() => act('cage', () => api.unlockViewingCage(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:unlock" width={13} class="text-ink-dim" />
          {$t('web.players.unlock_viewing_cage')}
        </button>
        <button type="button" onclick={() => act('unlock-techs', () => api.unlockPlayerTechnologies(uid))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:graduation-cap" width={13} class="text-ink-dim" />
          {$t('web.players.unlock_all_techs')}
        </button>
        <button type="button" onclick={() => act('max-abs', () => api.maxPlayerAbilities({ uids: [uid] }))} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-line/40 text-xs text-ink-secondary hover:bg-bg-hover hover:text-ink-primary transition-fast disabled:opacity-40">
          <Icon icon="lucide:zap" width={13} class="text-ink-dim" />
          {$t('web.players.max_all_abilities')}
        </button>
        <button type="button" onclick={handleDelete} disabled={saving} class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2 bg-bg-deep border border-status-error/40 text-xs text-status-error hover:bg-status-error/10 hover:border-status-error transition-fast disabled:opacity-40">
          <Icon icon="lucide:trash-2" width={13} />
          {$t('web.players.delete_player')}
        </button>
      </div>
    </div>
  </div>
{/if}
