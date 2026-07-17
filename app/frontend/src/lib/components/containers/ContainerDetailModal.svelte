<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import type { ContainerSummary, ContainerDetail as CDetail } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { container, onclose, onsaved }: {
    container: ContainerSummary;
    onclose: () => void;
    onsaved: () => void;
  } = $props();

  let detail = $state<CDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);

  let expandValue = $state(50);
  let expandEdit = $state(false);

  async function load() {
    loading = true; error = null;
    try { detail = await api.containerDetail(container.id); }
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
      if (name === 'clear' || name === 'expand') onsaved();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function doClear() {
    if (!confirm($t('web.containers.clear_confirm', { count: detail?.item_count ?? 0 }))) return;
    await doAction('clear', () => api.clearContainer(container.id));
  }

  async function doExpand() {
    await doAction('expand', () => api.expandContainer(container.id, { new_slot_count: expandValue }));
    expandEdit = false;
  }

  let typeColors: Record<string, string> = {
    'Chest': 'bg-amber-500/10 text-amber-400',
    'Guild Chest': 'bg-purple-500/10 text-purple-400',
    'PalBox': 'bg-green-500/10 text-green-400',
    'Booth': 'bg-pink-500/10 text-pink-400',
    'Refrigerator': 'bg-sky-500/10 text-sky-400',
    'Feed Box': 'bg-orange-500/10 text-orange-400',
    'Ammo Box': 'bg-red-500/10 text-red-400',
    'Storage Box': 'bg-blue-500/10 text-blue-400',
    'Item Box': 'bg-cyan-500/10 text-cyan-400',
    'Container': 'bg-neutral-500/10 text-neutral-400',
  };

  function typeClass(t: string): string {
    return typeColors[t] ?? 'bg-neutral-500/10 text-neutral-400';
  }

  function itemId(name: string): string {
    return name.replace(/^Item_/, '').replace(/_/g, ' ');
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()} role="dialog" tabindex="-1">
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-xl w-full mx-4 max-h-[85vh] overflow-y-auto animate-scale-in"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:box" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">
          <span class="px-2 py-0.5 rounded text-xs font-medium {typeClass(container.container_type)}">
            {container.container_type}
          </span>
        </h2>
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
        <div><span class="text-ink-muted">{$t('web.containers.detail_items')}</span> <span class="tabular-nums text-ink-primary font-medium">{detail.item_count}</span></div>
        <div><span class="text-ink-muted">{$t('web.containers.detail_slots')}</span> <span class="tabular-nums">{detail.slot_count}</span></div>
        <div><span class="text-ink-muted">{$t('web.containers.detail_guild')}</span> <span>{container.guild_name ?? container.guild_id?.slice(0, 13) ?? '—'}</span></div>
        <div class="col-span-2">
          <span class="text-ink-muted">{$t('web.containers.detail_container_id')}</span>
          <code class="text-xs font-mono text-ink-muted ml-1 break-all">{detail.id}</code>
        </div>
      </div>

      <!-- actions -->
      <div class="p-4 space-y-3">
        {#if actionError}
          <p class="text-xs text-status-error">{actionError}</p>
        {/if}

        <p class="text-xs uppercase tracking-wider text-ink-muted font-medium">{$t('web.common.actions')}</p>

        <!-- Clear -->
        <Button variant="danger" onclick={doClear} disabled={actionLoading !== null || detail.item_count === 0}>
          <Icon icon="lucide:eraser" width={14} class="mr-1" /> {$t('web.containers.clear_all_items')}
        </Button>

        <!-- Expand -->
        {#if expandEdit}
          <div class="flex gap-2 items-center">
            <label class="text-xs text-ink-muted">
              {$t('web.containers.new_slot_count')}
              <input class="input w-24 text-sm ml-1" type="number" min={detail.slot_count} max={500} bind:value={expandValue} />
            </label>
            <Button variant="primary" onclick={doExpand} disabled={actionLoading !== null}>{$t('web.common.set')}</Button>
            <Button variant="ghost" onclick={() => expandEdit = false}>{$t('web.common.cancel')}</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={() => { if (detail) { expandValue = detail.slot_count; } expandEdit = true; }} disabled={actionLoading !== null}>
            <Icon icon="lucide:maximize" width={14} class="mr-1" /> {$t('web.containers.expand_capacity')}
          </Button>
        {/if}
      </div>

      <!-- items list -->
      {#if detail.items.length > 0}
        <div class="border-t border-line/20 p-4 space-y-2">
          <p class="text-xs uppercase tracking-wider text-ink-muted font-medium">{$t('web.containers.items_count', { count: detail.items.length })}</p>
          <div class="max-h-56 overflow-y-auto space-y-1">
            {#each detail.items as item}
              {#if item.count > 0}
                <div class="flex items-center justify-between py-1.5 px-2 rounded bg-bg-hover/30 text-xs">
                  <span class="text-ink-primary truncate mr-2">{itemId(item.static_id)}</span>
                  <span class="tabular-nums text-ink-muted shrink-0">
                    <Badge tone={item.count > 0 ? 'accent' : 'neutral'}>{item.count}</Badge>
                  </span>
                </div>
              {/if}
            {/each}
          </div>
        </div>
      {:else}
        <div class="border-t border-line/20 p-4 text-center text-xs text-ink-dim">
          {$t('web.containers.empty')}
        </div>
      {/if}
    {/if}
  </div>
</div>
