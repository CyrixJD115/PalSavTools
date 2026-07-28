<script lang="ts">
  // Player Editor — the full player management suite.
  //
  // Renamed from "Player Inventory" since it now covers far more than bags:
  // Inventory / Stats / Tech Tree / Pals / Effigies / Missions.
  //
  // Supports a deep-link via ?uid=<uid> query param: the Players-tab popup
  // opens this page with a specific player pre-selected. Reads the param on
  // mount via $page.url.searchParams.
  //
  // Inventory reads (bags + equipment + dynamic items) all flow through the
  // world service's lazy build_mini_wsd path — no full level_dict
  // materialization. Player .sav reads are cache-first via player_savs LRU.
  import { saveLoaded, t } from '$stores/index';
  import { toast } from '$stores/toast';
  import { api } from '$lib/api/client';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Button from '$components/ui/Button.svelte';
  import Icon from '@iconify/svelte';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { loadItemMap } from '$lib/utils/items';
  import { loadTechnologies } from '$lib/utils/technologies';
  import BagTabs from '$components/inventory/BagTabs.svelte';
  import ItemGrid from '$components/inventory/ItemGrid.svelte';
  import EquipmentSlots from '$components/inventory/EquipmentSlots.svelte';
  import StatsEditor from '$components/inventory/StatsEditor.svelte';
  import TechTreePanel from '$components/inventory/TechTreePanel.svelte';
  import PartyPalboxPanel from '$components/inventory/PartyPalboxPanel.svelte';
  import PartyPalboxModal from '$components/inventory/PartyPalboxModal.svelte';
  import InfoPanel from '$components/players/InfoPanel.svelte';
  import EffigiesPanel from '$components/players/EffigiesPanel.svelte';
  import MissionsPanel from '$components/players/MissionsPanel.svelte';
  import ItemContextMenu from '$components/inventory/ItemContextMenu.svelte';
  import SetCountModal from '$components/inventory/SetCountModal.svelte';
  import type {
    ContainerItemSlot, PalGroupedResponse, PlayerInventoryResponse,
    PlayerStatsResponse, PlayerSummary, PlayerTechPointsResponse,
  } from '$types/index';

  // ---- top-level state ----
  type Tab = 'info' | 'inventory' | 'stats' | 'tech' | 'pals' | 'effigies' | 'missions';
  let activeTab = $state<Tab>('info');

  let players = $state<PlayerSummary[]>([]);
  let selectedUid = $state<string | null>(null);
  let inv = $state<PlayerInventoryResponse | null>(null);
  let loading = $state(false);
  let playersLoading = $state(false);
  let error = $state<string | null>(null);

  // ---- inventory-tab state ----
  let activeBag = $state<string>('common');
  let contextMenu = $state<{ slot: ContainerItemSlot; x: number; y: number } | null>(null);
  let setCountSlot = $state<ContainerItemSlot | null>(null);
  let bagSearch = $state('');
  let bagSort = $state<'slot' | 'name' | 'count'>('slot');

  // ---- sideband state (stats + tech points + pals) ----
  let palGrouped = $state<PalGroupedResponse | null>(null);
  let statsData = $state<PlayerStatsResponse | null>(null);
  let techPointsData = $state<PlayerTechPointsResponse | null>(null);
  let playerLevel = $state(1);

  // ---- modal open states (header quick-access) ----
  let showPartyPalbox = $state(false);

  let loadReqId = 0;

  const TABS: { id: Tab; labelKey: string; fallback: string; icon: string }[] = [
    { id: 'info',      labelKey: 'web.player_editor.info',     fallback: 'Info',     icon: 'lucide:info' },
    { id: 'inventory', labelKey: 'web.inventory.tab_inventory', fallback: 'Inventory', icon: 'lucide:backpack' },
    { id: 'stats',     labelKey: 'web.inventory.tab_stats',     fallback: 'Stats',     icon: 'lucide:activity' },
    { id: 'tech',      labelKey: 'web.inventory.tab_tech',      fallback: 'Tech Tree', icon: 'lucide:git-branch' },
    { id: 'pals',      labelKey: 'web.inventory.tab_pals',      fallback: 'Pals',      icon: 'lucide:paw-print' },
    { id: 'effigies',  labelKey: 'web.players.edit_effigies',   fallback: 'Effigies',  icon: 'lucide:gem' },
    { id: 'missions',  labelKey: 'web.players.edit_missions',   fallback: 'Missions',  icon: 'lucide:scroll-text' },
  ];

  $effect(() => {
    if ($saveLoaded) {
      if (players.length === 0 && !playersLoading) void loadPlayers();
    } else {
      players = []; inv = null; selectedUid = null; palGrouped = null;
      statsData = null; techPointsData = null; playerLevel = 1;
    }
  });

  onMount(() => {
    void loadItemMap();
    void loadTechnologies();
  });

  async function loadPlayers() {
    playersLoading = true; error = null;
    try {
      const res = await api.players({ limit: 200 });
      players = res.players;
      // Check for deep-link: ?uid= from the Players-tab popup.
      const deepUid = $page.url.searchParams.get('uid');
      const target = deepUid
        ? players.find((p) => p.uid === deepUid) ?? players[0]
        : players[0];
      if (target) await selectPlayer(target.uid);
      else loading = false;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      loading = false;
    } finally {
      playersLoading = false;
    }
  }

	  async function selectPlayer(uid: string) {
	    selectedUid = uid;
	    palGrouped = null;
	    await loadInventory();
	    void ensurePalGrouped();
	  }

  async function loadInventory() {
    if (!selectedUid) return;
    const reqId = ++loadReqId;
    loading = true; error = null;
    try {
      const [data, stats, techPts] = await Promise.all([
        api.playerInventory(selectedUid),
        api.playerStats(selectedUid).catch(() => null),
        api.playerTechPoints(selectedUid).catch(() => null),
      ]);
      if (reqId !== loadReqId) return;
      inv = data;
      statsData = stats;
      techPointsData = techPts;
      const selected = players.find((p) => p.uid === selectedUid);
      playerLevel = selected?.level ?? 1;
      const valid = data.bags.some((b) => b.bag_type === activeBag);
      if (!valid && data.bags.length > 0) activeBag = data.bags[0].bag_type;
    } catch (e) {
      if (reqId === loadReqId) error = e instanceof Error ? e.message : String(e);
    } finally {
      if (reqId === loadReqId) loading = false;
    }
  }

  async function refreshSideband() {
    if (!selectedUid) return;
    try {
      const [stats, techPts] = await Promise.all([
        api.playerStats(selectedUid).catch(() => null),
        api.playerTechPoints(selectedUid).catch(() => null),
      ]);
      statsData = stats;
      techPointsData = techPts;
      const p = players.find((pp) => pp.uid === selectedUid);
      if (p) playerLevel = p.level;
    } catch { /* non-critical */ }
  }

  async function ensurePalGrouped() {
    if (palGrouped || !selectedUid) return;
    try {
      palGrouped = await api.palGrouped(selectedUid);
    } catch { /* the Pals tab shows its own error */ }
  }

  // ---- inventory bag handlers ----
  const activeBagData = $derived(inv?.bags.find((b) => b.bag_type === activeBag) ?? null);

  const displayItems = $derived.by(() => {
    if (!activeBagData?.items) return [];
    const q = bagSearch.trim().toLowerCase();
    let items = activeBagData.items;
    if (q) items = items.filter((it) => it.static_id.toLowerCase().includes(q));
    if (bagSort === 'name') items = [...items].sort((a, b) => a.static_id.localeCompare(b.static_id));
    else if (bagSort === 'count') items = [...items].sort((a, b) => b.count - a.count);
    return items;
  });

  function sortBag() {
    bagSort = bagSort === 'slot' ? 'name' : bagSort === 'name' ? 'count' : 'slot';
  }

  function onSlotClick(slot: ContainerItemSlot) { setCountSlot = slot; }
  function onSlotContext(slot: ContainerItemSlot, e: MouseEvent) {
    contextMenu = { slot, x: e.clientX, y: e.clientY };
  }

  async function handleSetCount(newCount: number) {
    if (!setCountSlot || !activeBagData?.container_id) return;
    await api.setSlotCount(activeBagData.container_id, {
      slot_index: setCountSlot.slot_index, new_count: newCount,
    });
    toast.success($t('web.inventory.count_updated', 'Stack count updated.'));
    await loadInventory();
  }

  async function handleDelete(slot: ContainerItemSlot) {
    if (!activeBagData?.container_id) return;
    if (!confirm($t('web.inventory.delete_confirm', 'Remove this item from the slot?'))) return;
    await api.deleteSlot(activeBagData.container_id, slot.slot_index);
    toast.success($t('web.inventory.item_deleted', 'Item removed.'));
    await loadInventory();
  }

  async function handleClearBag() {
    if (!activeBagData?.container_id || activeBagData.item_count === 0) return;
    if (!confirm($t('web.inventory.clear_bag_confirm', { count: activeBagData.item_count }))) return;
    await api.clearContainer(activeBagData.container_id);
    toast.success($t('web.inventory.bag_cleared', 'Bag cleared.'));
    await loadInventory();
  }
</script>

<SaveGate icon="lucide:user-cog">
  <div class="p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
    <!-- header row: title + player select + quick-access modals -->
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.inventory.title', 'Player Editor')}</h1>
        <p class="text-xs text-ink-muted">
          {#if loading || playersLoading}
            {$t('web.common.loading', 'Loading\u2026')}
          {:else if inv}
            {$t('web.inventory.player_label', 'Player')}: <span class="text-ink-secondary font-medium">{inv.name}</span>
          {/if}
        </p>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <label for="pe-player" class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">
          {$t('web.inventory.select_player', 'Player')}
        </label>
        <select
          id="pe-player"
          class="input text-sm w-auto min-w-48"
          value={selectedUid ?? ''}
          onchange={(e) => selectPlayer((e.currentTarget as HTMLSelectElement).value)}
          disabled={playersLoading}
        >
          {#each players as p (p.uid)}
            <option value={p.uid}>{p.name}</option>
          {/each}
        </select>

          {#if inv}
            <Button variant="secondary" onclick={() => (showPartyPalbox = true)} class="!text-xs">
              <Icon icon="lucide:paw-print" width={13} class="mr-1" />
              {$t('web.inventory.party_palbox_button', 'Party')}
            </Button>
          {/if}
        </div>
      </div>

    {#if error}
      <p class="text-sm text-status-error p-3 rounded-4 bg-status-error/10 border border-status-error/30">{error}</p>
    {/if}

    {#if loading || playersLoading}
      <div class="flex justify-center py-16"><Spinner size={24} /></div>
    {:else if !inv}
      <EmptyState icon="lucide:user-cog" title={$t('web.inventory.no_data_title', 'No editor data')}>
        <p class="text-xs">{$t('web.inventory.no_data_body', 'Select a player to view and edit.')}</p>
      </EmptyState>
    {:else}
      <!-- sub-tab strip -->
      <div class="flex gap-1.5 border-b border-line/30 pb-2 overflow-x-auto">
        {#each TABS as tab (tab.id)}
          <button
            class="flex items-center gap-1.5 px-3.5 py-2 rounded-4 text-sm font-medium transition-all whitespace-nowrap
              {activeTab === tab.id
                ? 'bg-accent/15 text-accent border border-accent/40'
                : 'text-ink-secondary hover:bg-bg-hover border border-transparent'}"
            onclick={() => (activeTab = tab.id)}
          >
            <Icon icon={tab.icon} width={15} />
            {$t(tab.labelKey, tab.fallback)}
            {#if tab.id === 'pals' && palGrouped}
              <span class="text-[10px] text-ink-dim ml-0.5">{palGrouped.party.length + palGrouped.palbox.length}</span>
            {/if}
          </button>
        {/each}
	      </div>

	      <!-- ───── INFO TAB ───── -->
	      {#if activeTab === 'info' && selectedUid}
	        <InfoPanel uid={selectedUid} />
	      {/if}

	      <!-- ───── INVENTORY TAB ───── -->
      {#if activeTab === 'inventory'}
        <div class="card p-4 space-y-4">
          <EquipmentSlots
            armorBag={inv.bags.find((b) => b.bag_type === 'armor')}
            weaponBag={inv.bags.find((b) => b.bag_type === 'weapon')}
            foodBag={inv.bags.find((b) => b.bag_type === 'food')}
            onclick={onSlotClick}
            oncontextmenu={onSlotContext}
          />
          <div class="border-t border-line/20"></div>
          <BagTabs bags={inv.bags} active={activeBag} onchange={(bt) => (activeBag = bt)} />
          {#if activeBagData}
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <div class="flex items-center gap-2 text-xs text-ink-muted">
                <Badge tone={activeBagData.item_count > 0 ? 'accent' : 'neutral'}>
                  {activeBagData.item_count} {$t('web.inventory.items', 'items')}
                </Badge>
                <span>/ {activeBagData.slot_count} {$t('web.inventory.slots', 'slots')}</span>
                {#if !activeBagData.container_id}
                  <Badge tone="warning">{$t('web.inventory.not_allocated', 'Not allocated')}</Badge>
                {/if}
              </div>
              <div class="flex items-center gap-2">
                <div class="relative">
                  <Icon icon="lucide:search" width={12} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
                  <input type="text" class="input text-xs pl-7 w-32" placeholder={$t('web.inventory.bag_search', 'Filter\u2026')} bind:value={bagSearch} />
                </div>
                <span title={$t('web.inventory.sort_by', 'Sort')}>
                  <Button variant="ghost" onclick={sortBag} class="!text-xs !py-1 !px-2">
                    <Icon icon={bagSort === 'slot' ? 'lucide:arrow-down-narrow-wide' : bagSort === 'name' ? 'lucide:arrow-down-a-z' : 'lucide:arrow-down-0-1'} width={12} class="mr-1" />
                    {bagSort}
                  </Button>
                </span>
                <Button variant="ghost" onclick={() => void loadInventory()} disabled={loading}>
                  <Icon icon="lucide:refresh-cw" width={13} class="mr-1" />
                  {$t('web.common.refresh', 'Refresh')}
                </Button>
                <Button variant="danger" onclick={handleClearBag} disabled={activeBagData.item_count === 0 || !activeBagData.container_id}>
                  <Icon icon="lucide:eraser" width={13} class="mr-1" />
                  {$t('web.inventory.clear_bag', 'Clear Bag')}
                </Button>
              </div>
            </div>
            {#if activeBagData.container_id}
              <ItemGrid items={displayItems} slotCount={activeBagData.slot_count}
                cols={activeBag === 'weapon' || activeBag === 'armor' || activeBag === 'food' ? 6 : 10}
                onclick={onSlotClick} oncontextmenu={onSlotContext}
              />
            {:else}
              <EmptyState icon="lucide:package-x" title={$t('web.inventory.bag_not_allocated_title', 'Bag not allocated')}>
                <p class="text-xs">{$t('web.inventory.bag_not_allocated_body', "This player's .sav doesn't define this bag.")}</p>
              </EmptyState>
            {/if}
          {/if}
        </div>
      {/if}

      <!-- ───── STATS TAB ───── -->
      {#if activeTab === 'stats'}
        <div class="card p-4 max-w-xl mx-auto">
          <StatsEditor uid={selectedUid ?? ''} stats={statsData} techPoints={techPointsData} level={playerLevel} />
        </div>
      {/if}

      <!-- ───── TECH TREE TAB ───── -->
      {#if activeTab === 'tech' && selectedUid}
        <div class="card p-0 h-[70vh] flex flex-col overflow-hidden">
          <TechTreePanel uid={selectedUid} />
        </div>
      {/if}

      <!-- ───── PALS TAB ───── -->
      {#if activeTab === 'pals' && selectedUid}
        <div class="card p-0 max-h-[70vh] overflow-y-auto">
          <PartyPalboxPanel uid={selectedUid} partyId={inv.party_id} palboxId={inv.palbox_id} />
        </div>
      {/if}

      <!-- ───── EFFIGIES TAB ───── -->
      {#if activeTab === 'effigies' && selectedUid}
        <div class="card p-0">
          <EffigiesPanel uid={selectedUid} />
        </div>
      {/if}

      <!-- ───── MISSIONS TAB ───── -->
      {#if activeTab === 'missions' && selectedUid}
        <div class="card p-0">
          <MissionsPanel uid={selectedUid} />
        </div>
      {/if}
    {/if}
  </div>
</SaveGate>

<!-- modals -->
{#if contextMenu}
  <ItemContextMenu slot={contextMenu.slot} x={contextMenu.x} y={contextMenu.y}
    onclose={() => (contextMenu = null)}
    onsetcount={(s) => (setCountSlot = s)}
    ondelete={handleDelete}
  />
{/if}
{#if setCountSlot}
  <SetCountModal slot={setCountSlot} onclose={() => (setCountSlot = null)} onsubmit={handleSetCount} />
{/if}
{#if showPartyPalbox && selectedUid}
  <PartyPalboxModal uid={selectedUid} partyId={inv?.party_id ?? null} palboxId={inv?.palbox_id ?? null}
    onclose={() => { showPartyPalbox = false; }}
  />
{/if}
