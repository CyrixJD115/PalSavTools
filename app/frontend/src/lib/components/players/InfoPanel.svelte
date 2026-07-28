<script lang="ts">
  // Player Info panel — summary readout + all quick actions.
  // Renders as the default sub-tab in Player Editor.
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

  async function save(label: string, fn: () => Promise<unknown>) {
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

  function handleRename() {
    if (!renameValue.trim()) return;
    save('rename', () => api.renamePlayer(uid, { name: renameValue.trim() }));
  }

  function handleLevel() {
    save('level', () => api.setPlayerLevel(uid, { level: levelValue }));
  }

  function handleDelete() {
    if (!confirm($t('web.players.delete_confirm', { name: detail?.name ?? uid }))) return;
    save('delete', () => api.deletePlayer(uid));
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else if detail}
  <div class="p-5 max-w-2xl mx-auto space-y-6">
    <!-- summary readout -->
    <div class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
      <div><span class="text-ink-muted">{$t('web.players.detail_level')}</span> <span class="tabular-nums text-ink-primary font-medium ml-1">{detail.level}</span></div>
      <div><span class="text-ink-muted">{$t('web.players.detail_pals_owned')}</span> <span class="tabular-nums text-ink-primary font-medium ml-1">{detail.pal_count}</span></div>
      <div><span class="text-ink-muted">{$t('web.players.detail_guild')}</span> <Badge tone="accent" class="ml-1">{detail.guild_name ?? '—'}</Badge></div>
      <div><span class="text-ink-muted">{$t('web.players.detail_guild_level')}</span> <span class="tabular-nums ml-1">{detail.guild_level}</span></div>
      <div class="col-span-2"><span class="text-ink-muted">{$t('web.players.detail_last_seen')}</span> <span class="tabular-nums ml-1">{detail.last_seen_text ?? 'Unknown'}</span></div>
      <div class="col-span-2">
        <span class="text-ink-muted">{$t('web.players.detail_uid')}</span>
        <code class="text-xs font-mono text-ink-muted ml-2 break-all">{detail.uid}</code>
      </div>
    </div>

    <!-- inline editors -->
    <div class="border-t border-line/20 pt-4 space-y-3">
      <!-- Rename -->
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-xs font-medium text-ink-muted">{$t('web.common.rename')}</span>
        {#if editingName}
          <input class="input text-sm flex-1 max-w-xs" bind:value={renameValue} disabled={saving} />
          <Button variant="primary" onclick={handleRename} disabled={saving} class="!text-xs">{$t('web.common.save')}</Button>
          <Button variant="ghost" onclick={() => editingName = false} class="!text-xs">{$t('web.common.cancel')}</Button>
        {:else}
          <Button variant="secondary" onclick={() => { renameValue = detail.name; editingName = true; editingLevel = false; }} disabled={saving} class="!text-xs">
            <Icon icon="lucide:pencil" width={12} class="mr-1" />
            {detail.name}
          </Button>
        {/if}
      </div>
      <!-- Set Level -->
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-xs font-medium text-ink-muted">{$t('web.players.set_level')}</span>
        {#if editingLevel}
          <input class="input w-20 text-sm" type="number" min="1" max="80" bind:value={levelValue} disabled={saving} />
          <Button variant="primary" onclick={handleLevel} disabled={saving} class="!text-xs">{$t('web.common.save')}</Button>
          <Button variant="ghost" onclick={() => editingLevel = false} class="!text-xs">{$t('web.common.cancel')}</Button>
        {:else}
          <Button variant="secondary" onclick={() => { levelValue = detail.level; editingLevel = true; editingName = false; }} disabled={saving} class="!text-xs">
            <Icon icon="lucide:trending-up" width={12} class="mr-1" />
            {detail.level}
          </Button>
        {/if}
      </div>
    </div>

    <!-- one-click actions -->
    <div class="border-t border-line/20 pt-4">
      <p class="text-xs uppercase tracking-wider text-ink-muted font-semibold mb-3">{$t('web.common.actions')}</p>
      <div class="flex flex-wrap gap-2">
        <Button variant="secondary" onclick={async () => { try { await api.resetPlayerTimestamp(uid); await load(); toast.success($t('web.players.reset_timestamp')); } catch(e) { toast.error(e instanceof Error ? e.message : String(e)); }}} disabled={saving} class="!text-xs">
          <Icon icon="lucide:clock" width={13} class="mr-1" /> {$t('web.players.reset_timestamp')}
        </Button>
        <Button variant="secondary" onclick={async () => { try { await api.unlockViewingCage(uid); await load(); toast.success($t('web.players.unlock_viewing_cage')); } catch(e) { toast.error(e instanceof Error ? e.message : String(e)); }}} disabled={saving} class="!text-xs">
          <Icon icon="lucide:unlock" width={13} class="mr-1" /> {$t('web.players.unlock_viewing_cage')}
        </Button>
        <Button variant="secondary" onclick={async () => { try { await api.unlockPlayerTechnologies(uid); await load(); toast.success($t('web.players.unlock_all_techs')); } catch(e) { toast.error(e instanceof Error ? e.message : String(e)); }}} disabled={saving} class="!text-xs">
          <Icon icon="lucide:graduation-cap" width={13} class="mr-1" /> {$t('web.players.unlock_all_techs')}
        </Button>
        <Button variant="secondary" onclick={async () => { try { await api.maxPlayerAbilities({ uids: [uid] }); await load(); toast.success($t('web.players.max_all_abilities')); } catch(e) { toast.error(e instanceof Error ? e.message : String(e)); }}} disabled={saving} class="!text-xs">
          <Icon icon="lucide:zap" width={13} class="mr-1" /> {$t('web.players.max_all_abilities')}
        </Button>
        <Button variant="danger" onclick={handleDelete} disabled={saving} class="!text-xs">
          <Icon icon="lucide:trash-2" width={13} class="mr-1" /> {$t('web.players.delete_player')}
        </Button>
      </div>
    </div>
  </div>
{/if}
