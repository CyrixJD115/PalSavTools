<script lang="ts">
  // Pal Editor — PSP-style container-grouped grid layout.
  // Player selector + zone context (Party column always visible on the left,
  // Palbox grid as the main pane). Multi-select via Ctrl/Cmd-click; bulk
  // actions reuse the already-verified pal_service mutators.
  import { onMount } from 'svelte';
  import { saveLoaded, t } from '$stores/index';
  import { api } from '$lib/api/client';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import Icon from '@iconify/svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import PartyColumn from '$components/pals/PartyColumn.svelte';
  import PalboxGrid from '$components/pals/PalboxGrid.svelte';
  import PalDetailModal from '$components/pals/PalDetailModal.svelte';
  import PresetManager from '$components/pals/PresetManager.svelte';
  import type { PalGroupedResponse, PalSummary, PlayerSummary } from '$types/index';

  let players = $state<PlayerSummary[]>([]);
  let selectedUid = $state<string | null>(null);
  let selectedPlayerLevel = $state(0);
  let grouped = $state<PalGroupedResponse | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let search = $state('');
  let sort = $state<'slot' | 'name' | 'level'>('slot');
  let cheatMode = $state(false);
  let selectedPalIds = $state<string[]>([]);
  let detailId = $state<string | null>(null);
  let detailName = $state('');
  let showPresets = $state(false);
  let bulkLoading = $state(false);

  onMount(async () => {
    if (!$saveLoaded) return;
    await loadPlayers();
  });

  async function loadPlayers() {
    try {
      const res = await api.players();
      players = res.players;
      // auto-select first player with pals
      const first = players.find((p) => p.pal_count > 0) ?? players[0];
      if (first) await selectPlayer(first.uid);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function selectPlayer(uid: string) {
    selectedUid = uid;
    selectedPalIds = [];
    selectedPlayerLevel = players.find((p) => p.uid === uid)?.level ?? 0;
    await loadGrouped();
  }

  async function loadGrouped() {
    if (!selectedUid) return;
    loading = true;
    error = null;
    try {
      grouped = await api.palGrouped(selectedUid);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function openDetail(pal: PalSummary) {
    detailId = pal.instance_id;
    detailName = pal.display_name ?? pal.character_id;
  }
  function closeDetail() {
    detailId = null;
  }

  function toggleSelect(pal: PalSummary) {
    if (selectedPalIds.includes(pal.instance_id)) {
      selectedPalIds = selectedPalIds.filter((id) => id !== pal.instance_id);
    } else {
      selectedPalIds = [...selectedPalIds, pal.instance_id];
    }
  }
  function selectAll() {
    if (!grouped) return;
    selectedPalIds = [...grouped.party, ...grouped.palbox].map((p) => p.instance_id);
  }
  function clearSelection() {
    selectedPalIds = [];
  }

  async function handleSwap(sourceId: string, targetId: string) {
    error = null;
    try {
      await api.swapPals(sourceId, targetId);
      await loadGrouped();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function bulkAction(name: string, fn: (id: string) => Promise<unknown>) {
    if (selectedPalIds.length === 0) return;
    bulkLoading = true;
    error = null;
    try {
      await Promise.all(selectedPalIds.map(fn));
      await loadGrouped();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      bulkLoading = false;
    }
  }
  const bulkMaxOut = () => bulkAction('max', (id) => api.maxOutPal(id, cheatMode));
  const bulkHeal = () => bulkAction('heal', (id) => api.healPal(id));

  const allPals = $derived(grouped ? [...grouped.party, ...grouped.palbox] : []);
</script>

<div class="p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
  <!-- header -->
  <div class="flex items-center justify-between gap-3 flex-wrap">
    <div>
      <h1 class="text-2xl font-bold heading-gradient">{$t('web.pal_editor.title')}</h1>
      <p class="text-sm text-ink-muted mt-1">
        {#if grouped}
          {$t('web.pal_editor.zone_counts', { party: grouped.party.length, palbox: grouped.palbox.length })}
        {/if}
      </p>
    </div>
    <div class="flex items-center gap-2 flex-wrap">
      <button
        class="px-2 py-1 rounded-4 text-[10px] font-medium transition-fast {cheatMode ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' : 'bg-bg-elevated text-ink-muted border border-line/40'}"
        onclick={() => (cheatMode = !cheatMode)}
        title="Cheat mode raises caps to 255"
      >🐛</button>
      <button class="btn text-xs" onclick={() => (showPresets = true)}>
        <Icon icon="lucide:layers" width={13} /> {$t('web.pal_editor.presets')}
      </button>
    </div>
  </div>

  {#if !$saveLoaded}
    <EmptyState icon="lucide:sparkles" title={$t('web.pal_editor.no_save_title')}>
      {$t('web.pal_editor.no_save_body')}
    </EmptyState>
  {:else}
    <!-- player selector -->
    <div class="flex items-center gap-2 flex-wrap">
      <label class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.pal_editor.player')}</label>
      <select
        class="input text-sm w-auto min-w-48"
        value={selectedUid ?? ''}
        onchange={(e) => selectPlayer((e.currentTarget as HTMLSelectElement).value)}
      >
        {#each players as p}
          <option value={p.uid}>{p.name} ({p.pal_count})</option>
        {/each}
      </select>
    </div>

    {#if error}
      <p class="text-xs text-rose-400">{error}</p>
    {/if}

    {#if loading}
      <div class="flex justify-center py-16"><Spinner /></div>
    {:else if grouped}
      <!-- multi-select bulk action bar -->
      {#if selectedPalIds.length > 0}
        <div class="flex items-center gap-2 p-2 rounded-4 bg-accent/10 border border-accent/30">
          <span class="text-xs font-medium text-accent">{$t('web.pal_editor.selected_count', { count: selectedPalIds.length })}</span>
          <button class="btn btn-primary text-xs" onclick={bulkMaxOut} disabled={bulkLoading}>
            <Icon icon="lucide:chevrons-up" width={12} /> {$t('web.pal_editor.max_out')}
          </button>
          <button class="btn text-xs" onclick={bulkHeal} disabled={bulkLoading}>
            <Icon icon="lucide:heart-pulse" width={12} /> {$t('web.pal_editor.heal')}
          </button>
          <button class="btn text-xs" onclick={() => (showPresets = true)}>
            <Icon icon="lucide:layers" width={12} /> {$t('web.pal_editor.apply_preset')}
          </button>
          <button class="btn text-xs ml-auto" onclick={clearSelection}>
            <Icon icon="lucide:x" width={12} /> {$t('web.pal_editor.clear')}
          </button>
        </div>
      {/if}

      <!-- main layout: party column + palbox grid -->
      <div class="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        <!-- PARTY (left column) -->
        <div class="card p-3">
          <PartyColumn
            pals={grouped.party}
            selectedIds={selectedPalIds}
            playerLevel={selectedPlayerLevel}
            onclick={openDetail}
            onselect={toggleSelect}
            onswap={handleSwap}
          />
        </div>

        <!-- PALBOX (right pane) -->
        <div class="card p-4">
          <!-- palbox toolbar -->
          <div class="flex items-center justify-between gap-2 mb-3 flex-wrap">
            <h3 class="text-sm font-semibold text-ink-emphasis">{$t('web.pal_editor.palbox_zone')}</h3>
            <div class="flex items-center gap-2">
              <div class="relative">
                <Icon icon="lucide:search" width={13} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
                <input
                  type="text" bind:value={search} placeholder={$t('web.pal_editor.search_placeholder')}
                  class="input text-xs pl-8 w-40"
                />
              </div>
              <select bind:value={sort} class="input text-xs w-auto">
                <option value="slot">{$t('web.pal_editor.sort_slot')}</option>
                <option value="name">{$t('web.pal_editor.sort_name')}</option>
                <option value="level">{$t('web.pal_editor.sort_level')}</option>
              </select>
              <button class="btn text-xs px-2 py-1" onclick={selectAll} title={$t('web.pal_editor.select_all')}>
                <Icon icon="lucide:check-square" width={13} />
              </button>
            </div>
          </div>

          <PalboxGrid
            pals={grouped.palbox}
            selectedIds={selectedPalIds}
            playerLevel={selectedPlayerLevel}
            {search}
            {sort}
            onclick={openDetail}
            onselect={toggleSelect}
            onswap={handleSwap}
          />
        </div>
      </div>

      <!-- ungrouped (base-deployed / other) — collapsed summary -->
      {#if grouped.ungrouped.length > 0}
        <details class="card p-3">
          <summary class="text-xs font-semibold text-ink-dim cursor-pointer flex items-center gap-1">
            <Icon icon="lucide:info" width={12} />
            {$t('web.pal_editor.ungrouped_count', { count: grouped.ungrouped.length })}
          </summary>
          <p class="text-[11px] text-ink-muted mt-2">
            {$t('web.pal_editor.ungrouped_hint')}
          </p>
        </details>
      {/if}
    {/if}
  {/if}
</div>

{#if detailId}
  <PalDetailModal
    instanceId={detailId}
    displayName={detailName}
    onclose={closeDetail}
    onupdated={loadGrouped}
  />
{/if}

{#if showPresets}
  <PresetManager
    onclose={() => (showPresets = false)}
    onapplied={() => { showPresets = false; loadGrouped(); }}
    palIds={allPals.map((p) => p.instance_id)}
  />
{/if}
