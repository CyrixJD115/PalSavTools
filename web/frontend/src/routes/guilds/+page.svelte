<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded } from '$stores/index';
  import type { GuildSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';
  import GuildDetailModal from '$components/guilds/GuildDetailModal.svelte';

  let guilds = $state<GuildSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedGuild = $state<GuildSummary | null>(null);
  let viewMode = $state<'grid' | 'list'>('grid');
  let sortCol = $state<'name' | 'members' | 'bases'>('name');
  let sortDir = $state<'asc' | 'desc'>('asc');

  async function load() {
    loading = true; error = null;
    try { guilds = (await api.guilds()).guilds; }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(() => { if ($saveLoaded) load(); });

  type SortCol = 'name' | 'members' | 'bases';

  function toggleSort(col: SortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
  }

  let sorted = $derived([...guilds].sort((a, b) => {
    let cmp = 0;
    if (sortCol === 'name') cmp = a.name.localeCompare(b.name);
    else if (sortCol === 'members') cmp = a.player_count - b.player_count;
    else if (sortCol === 'bases') cmp = a.base_count - b.base_count;
    return sortDir === 'asc' ? cmp : -cmp;
  }));

  function onDetailSaved() { load(); selectedGuild = null; }
</script>

<SaveGate icon="lucide:building-2">
  <div class="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold heading-gradient">Guilds</h1>
        <p class="text-xs text-ink-muted">{guilds.length} guilds</p>
      </div>
      <div class="flex items-center gap-1 bg-bg-surface border border-line/30 rounded-lg p-0.5">
        <button
          class="px-2.5 py-1.5 text-xs rounded-md transition-fast {viewMode === 'grid' ? 'bg-bg-hover text-ink-primary shadow-sm' : 'text-ink-muted hover:text-ink-primary'}"
          onclick={() => viewMode = 'grid'}
        >
          <Icon icon="lucide:grid-3x3" width={14} />
        </button>
        <button
          class="px-2.5 py-1.5 text-xs rounded-md transition-fast {viewMode === 'list' ? 'bg-bg-hover text-ink-primary shadow-sm' : 'text-ink-muted hover:text-ink-primary'}"
          onclick={() => viewMode = 'list'}
        >
          <Icon icon="lucide:list" width={14} />
        </button>
      </div>
    </div>

    {#if loading}
      <Card><div class="flex justify-center py-12"><Spinner size={24} /></div></Card>
    {:else if error}
      <Card><p class="text-sm text-status-error p-4">{error}</p></Card>
    {:else if viewMode === 'grid'}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {#each sorted as g (g.id)}
          <Card hover>
            <button class="w-full text-left" onclick={() => selectedGuild = g}>
              <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-2">
                  <Icon icon="lucide:building-2" width={18} class="text-accent" />
                  <h3 class="text-base font-semibold text-ink-emphasis">{g.name}</h3>
                </div>
                <Badge tone="neutral">{g.player_count} players</Badge>
              </div>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="flex items-center gap-2 text-ink-secondary">
                  <Icon icon="lucide:users" width={14} class="text-ink-muted" /> {g.player_count} members
                </div>
                <div class="flex items-center gap-2 text-ink-secondary">
                  <Icon icon="lucide:map-pin" width={14} class="text-ink-muted" /> {g.base_count} bases
                </div>
              </div>
              {#if g.leader_uid}
                <div class="mt-3 pt-3 border-t border-line/30 flex items-center gap-2 text-xs text-ink-muted">
                  <Icon icon="lucide:crown" width={12} class="text-amber-400" />
                  <span class="font-mono">{g.leader_uid}</span>
                </div>
              {/if}
            </button>
          </Card>
        {/each}
      </div>
    {:else}
      <Card>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-ink-muted border-b border-line/40">
                <th class="py-2 pr-4 font-medium cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('name')}>
                  <span class="inline-flex items-center gap-1">
                    Guild
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'name'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium text-right cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('members')}>
                  <span class="inline-flex items-center gap-1 justify-end">
                    Members
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'members'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium text-right cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('bases')}>
                  <span class="inline-flex items-center gap-1 justify-end">
                    Bases
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'bases'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium">Leader</th>
              </tr>
            </thead>
            <tbody>
              {#each sorted as g (g.id)}
                <tr
                  class="border-b border-line/20 hover:bg-bg-hover/50 transition-fast cursor-pointer"
                  onclick={() => selectedGuild = g}
                >
                  <td class="py-2.5 pr-4">
                    <span class="inline-flex items-center gap-1.5">
                      <Icon icon="lucide:building-2" width={13} class="text-ink-dim shrink-0" />
                      {g.name}
                    </span>
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">{g.player_count}</td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">{g.base_count}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-secondary">{g.leader_uid ? g.leader_uid.slice(0, 13) + '…' : '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </Card>
    {/if}
  </div>
</SaveGate>

{#if selectedGuild}
  <GuildDetailModal
    guild={selectedGuild}
    onclose={() => selectedGuild = null}
    onsaved={onDetailSaved}
  />
{/if}
