<script lang="ts">
  import { onMount } from 'svelte';
  import { scale } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import type { GuildSummary, GuildDetail } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { guild, onclose, onsaved }: {
    guild: GuildSummary;
    onclose: () => void;
    onsaved: () => void;
  } = $props();

  let detail = $state<GuildDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);

  let editingName = $state(false);
  let nameValue = $state('');
  let editingLevel = $state(false);
  let levelValue = $state(1);
  let editingLeader = $state(false);
  let leaderUid = $state('');
  let confirmDelete = $state(false);

  async function load() {
    loading = true; error = null;
    try { detail = await api.guildDetail(guild.id); }
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
      if (name === 'delete') onsaved();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function doRename() {
    if (!nameValue.trim()) return;
    await doAction('rename', () => api.renameGuild(guild.id, { name: nameValue.trim() }));
    editingName = false;
  }

  async function doSetLevel() {
    await doAction('set-level', () => api.setGuildLevel(guild.id, { level: levelValue }));
    editingLevel = false;
  }

  async function doSetLeader() {
    if (!leaderUid.trim()) return;
    await doAction('set-leader', () => api.setGuildLeader(guild.id, { player_uid: leaderUid.trim() }));
    editingLeader = false;
  }

  async function doRemoveMember(uid: string) {
    if (!confirm($t('web.guilds.remove_member_confirm', { uid: `${uid.slice(0, 13)}…` }))) return;
    await doAction('remove-member', () => api.removeGuildMember(guild.id, uid));
  }

  async function doDelete() {
    const name = detail?.name;
    if (!confirm(name ? $t('web.guilds.delete_confirm', { name }) : $t('web.guilds.delete_confirm_fallback'))) return;
    await doAction('delete', () => api.deleteGuild(guild.id));
  }

  function startName() { nameValue = detail?.name ?? ''; editingName = true; }
  function startLevel() { levelValue = detail?.level ?? 1; editingLevel = true; }
  function startLeader() { leaderUid = ''; editingLeader = true; }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()} role="dialog" tabindex="-1">
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto animate-scale-in"
    transition:scale={{ start: 0.95, duration: 150 }}
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:building-2" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">{detail?.name ?? guild.name}</h2>
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
      <div class="grid grid-cols-3 gap-4 p-4 border-b border-line/20 text-sm">
        <div><span class="text-ink-muted">{$t('web.guilds.detail_level')}</span> <span class="tabular-nums text-ink-primary font-medium">{detail.level}</span></div>
        <div><span class="text-ink-muted">{$t('web.guilds.detail_members')}</span> <span class="tabular-nums">{detail.member_count}</span></div>
        <div><span class="text-ink-muted">{$t('web.guilds.detail_bases')}</span> <span class="tabular-nums">{detail.base_count}</span></div>
        <div class="col-span-3">
          <span class="text-ink-muted">{$t('web.guilds.detail_id')}</span>
          <code class="text-xs font-mono text-ink-muted ml-1 break-all">{detail.id}</code>
        </div>
      </div>

      <!-- members table -->
      <div class="p-4 border-b border-line/20">
        <p class="text-xs uppercase tracking-wider text-ink-muted font-medium mb-2">
          {$t('web.guilds.members_count', { count: detail.members.length })}
        </p>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs uppercase tracking-wider text-ink-muted border-b border-line/30">
              <th class="py-1.5 pr-3 font-medium">{$t('web.common.name')}</th>
              <th class="py-1.5 pr-3 font-medium">{$t('web.common.role')}</th>
              <th class="py-1.5 pr-3 font-medium font-mono">{$t('web.guilds.player_uid')}</th>
              <th class="py-1.5 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {#each detail.members as m (m.uid)}
              <tr class="border-b border-line/10 text-xs">
                <td class="py-1.5 pr-3">{m.name}</td>
                <td class="py-1.5 pr-3">
                  {#if m.is_leader}
                    <Badge tone="amber">{$t('web.common.leader')}</Badge>
                  {:else}
                    <Badge tone="neutral">{$t('web.common.member')}</Badge>
                  {/if}
                </td>
                <td class="py-1.5 pr-3 font-mono text-ink-muted">{m.uid.slice(0, 13)}…</td>
                <td class="py-1.5">
                  {#if !m.is_leader}
                    <button
                      class="text-ink-muted hover:text-status-error transition-fast"
                      onclick={() => doRemoveMember(m.uid)}
                      disabled={actionLoading !== null}
                      title={$t('web.guilds.remove_member_title')}
                    >
                      <Icon icon="lucide:x-circle" width={14} />
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
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
            <input class="input flex-1 text-sm" bind:value={nameValue} placeholder={$t('web.guilds.rename_label')} />
            <Button variant="primary" onclick={doRename} disabled={actionLoading !== null}>{$t('web.common.save')}</Button>
            <Button variant="ghost" onclick={() => editingName = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startName} disabled={actionLoading !== null}>
            <Icon icon="lucide:pencil" width={14} class="mr-1" /> {$t('web.common.rename')}
          </Button>
        {/if}

        <!-- Set Level -->
        {#if editingLevel}
          <div class="flex gap-2 items-center">
            <input class="input w-24 text-sm" type="number" min="1" max="35" bind:value={levelValue} />
            <Button variant="primary" onclick={doSetLevel} disabled={actionLoading !== null}>{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => editingLevel = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startLevel} disabled={actionLoading !== null}>
            <Icon icon="lucide:trending-up" width={14} class="mr-1" /> {$t('web.guilds.set_level')}
          </Button>
        {/if}

        <!-- Set Leader -->
        {#if editingLeader}
          <div class="flex gap-2 items-center">
            <input class="input flex-1 text-sm" bind:value={leaderUid} placeholder={$t('web.guilds.player_uid')} />
            <Button variant="primary" onclick={doSetLeader} disabled={actionLoading !== null}>{$t('web.guilds.promote')}</Button>
            <Button variant="ghost" onclick={() => editingLeader = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startLeader} disabled={actionLoading !== null}>
            <Icon icon="lucide:crown" width={14} class="mr-1" /> {$t('web.guilds.set_leader')}
          </Button>
        {/if}

        <!-- Delete (danger) -->
        <div class="border-t border-line/20 pt-3">
          {#if confirmDelete}
            <div class="flex items-center gap-2 text-sm">
              <span class="text-status-error">{$t('web.guilds.delete_confirm_fallback')}</span>
              <Button variant="danger" onclick={doDelete} disabled={actionLoading !== null}>{$t('web.common.confirm')}</Button>
              <Button variant="ghost" onclick={() => confirmDelete = false}>{$t('web.common.cancel')}</Button>
            </div>
          {:else}
            <Button variant="danger" onclick={() => confirmDelete = true} disabled={actionLoading !== null}>
              <Icon icon="lucide:trash-2" width={14} class="mr-1" /> {$t('web.guilds.delete_guild')}
            </Button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>
