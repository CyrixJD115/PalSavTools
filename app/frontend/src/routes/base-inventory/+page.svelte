<script lang="ts">
  // Base Inventory — per-base storage chests + working pals.
  //
  // A base camp's chests are ItemContainerSaveData entries whose owning
  // MapObjectSaveData row has base_camp_id_belong_to == this base. The
  // backend's /bases/{id}/inventory endpoint returns them all (with slot
  // contents) in one shot, plus the base's working pals. Chests are
  // selectable from a left list; the right pane shows the selected chest's
  // grid + the worker pals panel below.
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
  import { loadItemMap } from '$lib/utils/items';
  import ItemGrid from '$components/inventory/ItemGrid.svelte';
  import ItemContextMenu from '$components/inventory/ItemContextMenu.svelte';
  import SetCountModal from '$components/inventory/SetCountModal.svelte';
  import WorkerPalGrid from '$components/inventory/WorkerPalGrid.svelte';
  import type {
    BaseInventoryResponse, BaseSummary, ContainerItemSlot,
  } from '$types/index';

  let bases = $state<BaseSummary[]>([]);
  let selectedBaseId = $state<string | null>(null);
  let data = $state<BaseInventoryResponse | null>(null);
  let loading = $state(false);
  let basesLoading = $state(false);
  let error = $state<string | null>(null);

  let selectedChestId = $state<string | null>(null);
  let contextMenu = $state<{ slot: ContainerItemSlot; x: number; y: number } | null>(null);
  let setCountSlot = $state<ContainerItemSlot | null>(null);

  let loadReqId = 0;

  $effect(() => {
    if ($saveLoaded) {
      if (bases.length === 0 && !basesLoading) void loadBases();
    } else {
      bases = []; data = null; selectedBaseId = null; selectedChestId = null;
    }
  });

  onMount(() => { void loadItemMap(); });

  async function loadBases() {
    basesLoading = true; error = null;
    try {
      const res = await api.bases({ limit: 200 });
      bases = res.bases;
      const first = bases[0];
      if (first) await selectBase(first.id);
      else loading = false;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      loading = false;
    } finally {
      basesLoading = false;
    }
  }

  async function selectBase(id: string) {
    selectedBaseId = id;
    selectedChestId = null;
    await loadInventory();
  }

  async function loadInventory() {
    if (!selectedBaseId) return;
    const reqId = ++loadReqId;
    loading = true; error = null;
    try {
      const d = await api.baseInventory(selectedBaseId);
      if (reqId !== loadReqId) return;
      data = d;
      if (d.containers.length > 0) selectedChestId = d.containers[0].id;
    } catch (e) {
      if (reqId === loadReqId) error = e instanceof Error ? e.message : String(e);
    } finally {
      if (reqId === loadReqId) loading = false;
    }
  }

  const selectedChest = $derived(
    data?.containers.find((c) => c.id === selectedChestId) ?? null
  );

  // ---- chest list item rendering --------------------------------------------

  const typeColors: Record<string, string> = {
    'Chest': 'bg-amber-500/10 text-amber-400',
    'Guild Chest': 'bg-purple-500/10 text-purple-400',
    'Storage Box': 'bg-blue-500/10 text-blue-400',
    'Item Box': 'bg-cyan-500/10 text-cyan-400',
    'Refrigerator': 'bg-sky-500/10 text-sky-400',
    'Feed Box': 'bg-orange-500/10 text-orange-400',
    'Ammo Box': 'bg-red-500/10 text-red-400',
    'Container': 'bg-neutral-500/10 text-neutral-400',
  };
  function typeClass(t: string): string {
    return typeColors[t] ?? 'bg-neutral-500/10 text-neutral-400';
  }

  function fmtVec(loc: [number, number, number] | null): string {
    if (!loc || (loc[0] === 0 && loc[1] === 0 && loc[2] === 0)) return '—';
    return `${loc[0].toFixed(0)}, ${loc[1].toFixed(0)}`;
  }

  // ---- per-slot mutations ----------------------------------------------------

  function onSlotClick(slot: ContainerItemSlot) { setCountSlot = slot; }
  function onSlotContext(slot: ContainerItemSlot, e: MouseEvent) {
    contextMenu = { slot, x: e.clientX, y: e.clientY };
  }

  async function handleSetCount(newCount: number) {
    if (!setCountSlot || !selectedChest) return;
    await api.setSlotCount(selectedChest.id, {
      slot_index: setCountSlot.slot_index, new_count: newCount,
    });
    toast.success($t('web.inventory.count_updated', 'Stack count updated.'));
    await loadInventory();
  }

  async function handleDelete(slot: ContainerItemSlot) {
    if (!selectedChest) return;
    if (!confirm($t('web.inventory.delete_confirm', 'Remove this item from the slot?'))) return;
    await api.deleteSlot(selectedChest.id, slot.slot_index);
    toast.success($t('web.inventory.item_deleted', 'Item removed.'));
    await loadInventory();
  }

  async function handleClearChest() {
    if (!selectedChest || selectedChest.item_count === 0) return;
    if (!confirm($t('web.base_inventory.clear_chest_confirm', {
      count: selectedChest.item_count,
    }))) return;
    await api.clearContainer(selectedChest.id);
    toast.success($t('web.base_inventory.chest_cleared', 'Chest cleared.'));
    await loadInventory();
  }
</script>

<SaveGate icon="lucide:warehouse">
  <div class="p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
    <!-- header -->
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.base_inventory.title', 'Base Inventory')}</h1>
        <p class="text-xs text-ink-muted">
          {#if loading || basesLoading}
            {$t('web.common.loading', 'Loading…')}
          {:else if data}
            {data.containers.length} {$t('web.base_inventory.chests', 'chests')}
            · {data.workers.length} {$t('web.base_inventory.workers_inline', 'workers')}
            {#if data.guild_name}· {data.guild_name}{/if}
          {/if}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <label for="bi-base" class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">
          {$t('web.base_inventory.select_base', 'Base')}
        </label>
        <select
          id="bi-base"
          class="input text-sm w-auto min-w-56"
          value={selectedBaseId ?? ''}
          onchange={(e) => selectBase((e.currentTarget as HTMLSelectElement).value)}
          disabled={basesLoading}
        >
          {#each bases as b (b.id)}
            <option value={b.id}>
              {b.guild_name ?? $t('web.base_inventory.base', 'Base')} #{b.base_position}
              {#if b.leader_name}- {b.leader_name}{/if}
            </option>
          {/each}
        </select>
      </div>
    </div>

    {#if error}
      <p class="text-sm text-status-error p-3 rounded-4 bg-status-error/10 border border-status-error/30">{error}</p>
    {/if}

    {#if loading || basesLoading}
      <div class="flex justify-center py-16"><Spinner size={24} /></div>
    {:else if !data}
      <EmptyState icon="lucide:warehouse" title={$t('web.base_inventory.no_data_title', 'No base inventory data')}>
        <p class="text-xs">{$t('web.base_inventory.no_data_body', 'Select a base camp to view its storage.')}</p>
      </EmptyState>
    {:else}
      <div class="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
        <!-- LEFT: chest list + worker pals -->
        <div class="space-y-3">
          <div class="card p-2">
            <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim px-2 py-1.5 flex items-center gap-1.5">
              <Icon icon="lucide:archive" width={11} />
              {$t('web.base_inventory.chests', 'Chests')}
            </p>
            {#if data.containers.length === 0}
              <p class="text-xs text-ink-dim px-2 py-4 text-center">{$t('web.base_inventory.no_chests', 'No storage containers at this base.')}</p>
            {:else}
              <div class="max-h-[40vh] overflow-y-auto space-y-0.5">
                {#each data.containers as c (c.id)}
                  <button
                    type="button"
                    class="w-full text-left px-2 py-2 rounded-4 transition-fast
                      {c.id === selectedChestId ? 'bg-accent/15 border border-accent/40' : 'hover:bg-bg-hover border border-transparent'}"
                    onclick={() => (selectedChestId = c.id)}
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="text-xs font-medium text-ink-primary truncate">{c.container_type}</span>
                      <Badge tone={c.item_count > 0 ? 'accent' : 'neutral'}>{c.item_count}/{c.slot_count}</Badge>
                    </div>
                    <p class="text-[10px] font-mono text-ink-dim truncate">{c.id.slice(0, 18)}…</p>
                  </button>
                {/each}
              </div>
            {/if}
          </div>

          <div class="card p-3">
            <WorkerPalGrid workers={data.workers} />
          </div>
        </div>

        <!-- RIGHT: selected chest grid -->
        <div class="card p-4 space-y-3">
          {#if !selectedChest}
            <EmptyState icon="lucide:box" title={$t('web.base_inventory.no_chest_selected_title', 'Select a chest')}>
              <p class="text-xs">{$t('web.base_inventory.no_chest_selected_body', 'Pick a container from the list to view its contents.')}</p>
            </EmptyState>
          {:else}
            <div class="flex items-center justify-between gap-2 flex-wrap border-b border-line/20 pb-3">
              <div class="flex items-center gap-2 min-w-0">
                <span class="px-2 py-0.5 rounded text-xs font-medium {typeClass(selectedChest.container_type)}">
                  {selectedChest.container_type}
                </span>
                <span class="text-xs text-ink-muted">
                  {selectedChest.item_count} {$t('web.inventory.items', 'items')} / {selectedChest.slot_count} {$t('web.inventory.slots', 'slots')}
                </span>
                <span class="text-[10px] font-mono text-ink-dim">{fmtVec(selectedChest.location)}</span>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="ghost" onclick={() => void loadInventory()} disabled={loading}>
                  <Icon icon="lucide:refresh-cw" width={13} class="mr-1" />
                  {$t('web.common.refresh', 'Refresh')}
                </Button>
                <Button
                  variant="danger"
                  onclick={handleClearChest}
                  disabled={selectedChest.item_count === 0}
                >
                  <Icon icon="lucide:eraser" width={13} class="mr-1" />
                  {$t('web.base_inventory.clear_chest', 'Clear Chest')}
                </Button>
              </div>
            </div>

            {#if selectedChest.item_count === 0}
              <EmptyState icon="lucide:box" title={$t('web.base_inventory.empty_chest', 'This chest is empty')} />
            {:else}
              <ItemGrid
                items={selectedChest.items}
                slotCount={selectedChest.slot_count}
                cols={10}
                onclick={onSlotClick}
                oncontextmenu={onSlotContext}
              />
            {/if}
          {/if}
        </div>
      </div>
    {/if}
  </div>
</SaveGate>

{#if contextMenu}
  <ItemContextMenu
    slot={contextMenu.slot}
    x={contextMenu.x}
    y={contextMenu.y}
    onclose={() => (contextMenu = null)}
    onsetcount={(s) => (setCountSlot = s)}
    ondelete={handleDelete}
  />
{/if}

{#if setCountSlot}
  <SetCountModal
    slot={setCountSlot}
    onclose={() => (setCountSlot = null)}
    onsubmit={handleSetCount}
  />
{/if}
