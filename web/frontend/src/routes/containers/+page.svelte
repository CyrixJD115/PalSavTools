<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded } from '$stores/index';
  import type { ContainerSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';
  import ContainerDetailModal from '$components/containers/ContainerDetailModal.svelte';

  let containers = $state<ContainerSummary[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedContainer = $state<ContainerSummary | null>(null);
  let query = $state('');
  let sortCol = $state<'type' | 'slots' | 'items' | 'guild'>('type');
  let sortDir = $state<'asc' | 'desc'>('asc');

  const LIMIT = 500;
  async function load() {
    loading = true; error = null;
    try { const r = await api.containers(LIMIT); containers = r.containers; total = r.total; }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(() => { if ($saveLoaded) load(); });

  type SortCol = 'type' | 'slots' | 'items' | 'guild';
  function toggleSort(col: SortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
  }

  const filtered = $derived(
    containers
      .filter((c) =>
        c.id.toLowerCase().includes(query.toLowerCase()) ||
        (c.owner_player_uid ?? '').toLowerCase().includes(query.toLowerCase()) ||
        (c.guild_name ?? c.guild_id ?? '').toLowerCase().includes(query.toLowerCase()) ||
        c.container_type.toLowerCase().includes(query.toLowerCase()),
      )
      .sort((a, b) => {
        let cmp = 0;
        if (sortCol === 'type') cmp = a.container_type.localeCompare(b.container_type);
        else if (sortCol === 'slots') cmp = a.slot_count - b.slot_count;
        else if (sortCol === 'items') cmp = a.item_count - b.item_count;
        else if (sortCol === 'guild') cmp = (a.guild_name ?? '').localeCompare(b.guild_name ?? '');
        return sortDir === 'asc' ? cmp : -cmp;
      }),
  );

  let typeColors: Record<string, string> = {
    'Chest': 'bg-amber-500/10 text-amber-400',
    'Storage Box': 'bg-blue-500/10 text-blue-400',
    'Item Box': 'bg-cyan-500/10 text-cyan-400',
    'Guild Chest': 'bg-purple-500/10 text-purple-400',
    'PalBox': 'bg-green-500/10 text-green-400',
    'Booth': 'bg-pink-500/10 text-pink-400',
    'Refrigerator': 'bg-sky-500/10 text-sky-400',
    'Feed Box': 'bg-orange-500/10 text-orange-400',
    'Ammo Box': 'bg-red-500/10 text-red-400',
    'Container': 'bg-neutral-500/10 text-neutral-400',
  };

  function typeClass(type: string): string {
    return typeColors[type] ?? 'bg-neutral-500/10 text-neutral-400';
  }

  function onDetailSaved() { load(); selectedContainer = null; }

  function fmtVec(loc: [number, number, number] | null): string {
    if (!loc) return '—';
    if (loc[0] === 0 && loc[1] === 0 && loc[2] === 0) return '—';
    return `${loc[0].toFixed(0)}, ${loc[1].toFixed(0)}`;
  }
</script>

<SaveGate icon="lucide:box">
  <div class="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">Containers</h1>
        <p class="text-xs text-ink-muted">
          Showing first {containers.length} of {total} item containers
        </p>
      </div>
      <input class="input max-w-xs" placeholder="Filter by type, ID, guild..." bind:value={query} />
    </div>

    <Card>
      {#if loading}
        <div class="flex justify-center py-12"><Spinner size={24} /></div>
      {:else if error}
        <p class="text-sm text-status-error p-4">{error}</p>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-ink-muted border-b border-line/40">
                <th class="py-2 pr-4 font-medium cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('type')}>
                  <span class="inline-flex items-center gap-1">
                    Type
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'type'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium text-right cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('items')}>
                  <span class="inline-flex items-center gap-1 justify-end">
                    Items
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'items'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium text-right cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('slots')}>
                  <span class="inline-flex items-center gap-1 justify-end">
                    Slots
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'slots'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('guild')}>
                  <span class="inline-flex items-center gap-1">
                    Guild
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'guild'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium">Location</th>
                <th class="py-2 pr-4 font-medium font-mono">Container ID</th>
              </tr>
            </thead>
            <tbody>
              {#each filtered as c (c.id)}
                <tr
                  class="border-b border-line/20 hover:bg-bg-hover/50 transition-fast cursor-pointer"
                  onclick={() => selectedContainer = c}
                >
                  <td class="py-2.5 pr-4">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium {typeClass(c.container_type)}">
                      {c.container_type}
                    </span>
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">
                    {#if c.item_count > 0}
                      <span class="text-ink-primary font-medium">{c.item_count}</span>
                    {:else}
                      <span class="text-ink-dim">0</span>
                    {/if}
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums text-ink-secondary">{c.slot_count}</td>
                  <td class="py-2.5 pr-4 text-ink-secondary max-w-[10rem] truncate">{c.guild_name ?? c.guild_id?.slice(0, 13) ?? '—'}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-muted">{fmtVec(c.location)}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-muted">{c.id.slice(0, 18)}…</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if total > LIMIT}
          <p class="mt-3 text-xs text-ink-dim text-center">
            Refine the filter or increase the backend limit to see beyond the first {LIMIT}.
          </p>
        {/if}
      {/if}
    </Card>
  </div>
</SaveGate>

{#if selectedContainer}
  <ContainerDetailModal
    container={selectedContainer}
    onclose={() => selectedContainer = null}
    onsaved={onDetailSaved}
  />
{/if}
