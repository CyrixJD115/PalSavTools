<script lang="ts">
  import { onMount } from 'svelte';
  import { scale } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import type { BaseSummary, BaseDetail } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { base, onclose, onsaved }: {
    base: BaseSummary;
    onclose: () => void;
    onsaved: () => void;
  } = $props();

  let detail = $state<BaseDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);

  let editingGuildName = $state(false);
  let guildNameValue = $state('');
  let editingGuildLevel = $state(false);
  let guildLevelValue = $state(1);
  let editingRadius = $state(false);
  let radiusValue = $state(3500);
  let deleteWorkers = $state(false);

  async function load() {
    loading = true; error = null;
    try { detail = await api.baseDetail(base.id); }
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

  async function doRenameGuild() {
    if (!guildNameValue.trim()) return;
    await doAction('rename-guild', () => api.renameBaseGuild(base.id, { name: guildNameValue.trim() }));
    editingGuildName = false;
  }

  async function doSetGuildLevel() {
    await doAction('set-guild-level', () => api.setBaseGuildLevel(base.id, { level: guildLevelValue }));
    editingGuildLevel = false;
  }

  async function doSetRadius() {
    await doAction('set-radius', () => api.setBaseRadius(base.id, { radius: radiusValue }));
    editingRadius = false;
  }

  async function handleDelete() {
    if (!confirm(`Delete base of "${detail?.guild_name ?? 'Unknown'}"? This cannot be undone.`)) return;
    await doAction('delete', () => api.deleteBase(base.id, { delete_workers: deleteWorkers }));
  }

  function startGuildName() { guildNameValue = detail?.guild_name ?? ''; editingGuildName = true; }
  function startGuildLevel() { guildLevelValue = detail?.guild_level ?? 1; editingGuildLevel = true; }
  function startRadius() { radiusValue = detail?.area_range ?? 3500; editingRadius = true; }

  function fmtCoord(loc: [number, number, number] | null): string {
    if (!loc) return '—';
    return `X: ${loc[0].toFixed(0)}, Y: ${loc[1].toFixed(0)}, Z: ${loc[2].toFixed(0)}`;
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()} role="dialog" tabindex="-1">
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto animate-scale-in"
    transition:scale={{ start: 0.95, duration: 150 }}
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:building-2" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">{detail?.guild_name ?? base.guild_name ?? 'Base'}</h2>
        {#if base.base_position === 1}
          <Badge tone="amber">Main</Badge>
        {/if}
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
        <div><span class="text-ink-muted">Guild:</span> <Badge tone="accent">{detail.guild_name ?? '—'}</Badge></div>
        <div><span class="text-ink-muted">Guild Level:</span> <span class="tabular-nums text-ink-primary font-medium">{detail.guild_level}</span></div>
        <div><span class="text-ink-muted">Leader:</span> <span>{detail.leader_name ?? '—'}</span></div>
        <div><span class="text-ink-muted">Members:</span> <span class="tabular-nums">{detail.member_count}</span></div>
        <div><span class="text-ink-muted">Base:</span> <span class="tabular-nums">{detail.base_position}/{detail.total_bases}</span></div>
        <div><span class="text-ink-muted">Area Range:</span> <span class="tabular-nums font-mono text-xs">{(detail.area_range / 100).toFixed(0)}m</span></div>
        <div class="col-span-2"><span class="text-ink-muted">Location:</span> <span class="font-mono text-xs text-ink-secondary">{fmtCoord(detail.location)}</span></div>
        <div class="col-span-2">
          <span class="text-ink-muted">Base ID:</span>
          <code class="text-xs font-mono text-ink-muted ml-1 break-all">{detail.id}</code>
        </div>
      </div>

      <!-- actions -->
      <div class="p-4 space-y-3">
        {#if actionError}
          <p class="text-xs text-status-error">{actionError}</p>
        {/if}

        <p class="text-xs uppercase tracking-wider text-ink-muted font-medium">Actions</p>

        <!-- Rename Guild -->
        {#if editingGuildName}
          <div class="flex gap-2 items-center">
            <input class="input flex-1 text-sm" bind:value={guildNameValue} placeholder="New guild name" />
            <Button variant="primary" onclick={doRenameGuild} disabled={actionLoading !== null}>Save</Button>
            <Button variant="ghost" onclick={() => editingGuildName = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startGuildName} disabled={actionLoading !== null}>
            <Icon icon="lucide:pencil" width={14} class="mr-1" /> Rename Guild
          </Button>
        {/if}

        <!-- Set Guild Level -->
        {#if editingGuildLevel}
          <div class="flex gap-2 items-center">
            <input class="input w-24 text-sm" type="number" min="1" max="35" bind:value={guildLevelValue} />
            <Button variant="primary" onclick={doSetGuildLevel} disabled={actionLoading !== null}>Set</Button>
            <Button variant="ghost" onclick={() => editingGuildLevel = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startGuildLevel} disabled={actionLoading !== null}>
            <Icon icon="lucide:trending-up" width={14} class="mr-1" /> Set Guild Level
          </Button>
        {/if}

        <!-- Set Base Radius -->
        {#if editingRadius}
          <div class="flex gap-2 items-center flex-wrap">
            <label class="text-xs text-ink-muted">
              Radius (units):
              <input class="input w-28 text-sm ml-1" type="number" min="100" max="50000" bind:value={radiusValue} />
            </label>
            <span class="text-xs text-ink-muted">({(radiusValue / 100).toFixed(0)}m)</span>
            <Button variant="primary" onclick={doSetRadius} disabled={actionLoading !== null}>Set</Button>
            <Button variant="ghost" onclick={() => editingRadius = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startRadius} disabled={actionLoading !== null}>
            <Icon icon="lucide:maximize-2" width={14} class="mr-1" /> Adjust Area Range
          </Button>
        {/if}

        <!-- Delete (danger) -->
        <div class="border-t border-line/20 pt-3 space-y-2">
          <label class="flex items-center gap-2 text-xs text-ink-muted cursor-pointer">
            <input type="checkbox" bind:checked={deleteWorkers} />
            Also delete workers
          </label>
          <Button variant="danger" onclick={handleDelete} disabled={actionLoading !== null}>
            <Icon icon="lucide:trash-2" width={14} class="mr-1" /> Delete Base
          </Button>
        </div>
      </div>
    {/if}
  </div>
</div>
