<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded } from '$stores/index';
  import type { PlayerSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import PlayerDetailModal from '$components/players/PlayerDetailModal.svelte';

  let players = $state<PlayerSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let query = $state('');
  let sortKey = $state<'name' | 'level' | 'pal_count' | 'last_seen' | 'guild_name'>('name');
  let sortAsc = $state(true);
  let selectedUid = $state<string | null>(null);
  let selectedName = $state<string>('');

  async function load() {
    loading = true; error = null;
    try {
      const res = await api.players();
      players = res.players;
    } catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(() => { if ($saveLoaded) load(); });

  const filtered = $derived(
    players.filter((p) =>
      p.name.toLowerCase().includes(query.toLowerCase()) ||
      p.uid.toLowerCase().includes(query.toLowerCase()) ||
      (p.guild_name ?? '').toLowerCase().includes(query.toLowerCase()),
    ),
  );

  const sorted = $derived(
    [...filtered].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'level') cmp = a.level - b.level;
      else if (sortKey === 'pal_count') cmp = a.pal_count - b.pal_count;
      else if (sortKey === 'last_seen') cmp = (a.last_seen_seconds ?? 0) - (b.last_seen_seconds ?? 0);
      else if (sortKey === 'guild_name') cmp = (a.guild_name ?? '').localeCompare(b.guild_name ?? '');
      return sortAsc ? cmp : -cmp;
    }),
  );

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
  }

  const arrows = $derived.by(() => ({
    name: sortKey === 'name' ? (sortAsc ? '▲' : '▼') : null,
    level: sortKey === 'level' ? (sortAsc ? '▲' : '▼') : null,
    pal_count: sortKey === 'pal_count' ? (sortAsc ? '▲' : '▼') : null,
    guild_name: sortKey === 'guild_name' ? (sortAsc ? '▲' : '▼') : null,
    last_seen: sortKey === 'last_seen' ? (sortAsc ? '▲' : '▼') : null,
  }));

  function openDetail(p: PlayerSummary) {
    selectedUid = p.uid;
    selectedName = p.name;
  }

  function closeDetail() {
    selectedUid = null;
    selectedName = '';
  }

  function handleUpdated() {
    closeDetail();
    load();
  }
</script>

<SaveGate icon="lucide:users">
  <div class="p-6 max-w-6xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">Players</h1>
        <p class="text-xs text-ink-muted">{players.length} players across all guilds</p>
      </div>
      <input class="input max-w-xs" placeholder="Filter by name, UID, guild..." bind:value={query} />
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
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('name')}>
                  <span class="inline-flex items-center gap-1">Name<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.name}>{arrows.name || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('level')}>
                  <span class="inline-flex items-center gap-1">Lv<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.level}>{arrows.level || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('pal_count')}>
                  <span class="inline-flex items-center gap-1">Pals<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.pal_count}>{arrows.pal_count || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('guild_name')}>
                  <span class="inline-flex items-center gap-1">Guild<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.guild_name}>{arrows.guild_name || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium select-none">GLv</th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('last_seen')}>
                  <span class="inline-flex items-center gap-1">Last seen<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.last_seen}>{arrows.last_seen || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium font-mono select-none">UID</th>
              </tr>
            </thead>
            <tbody>
              {#each sorted as p (p.uid)}
                <tr class="border-b border-line/20 hover:bg-bg-hover/50 transition-fast cursor-pointer" onclick={() => openDetail(p)}>
                  <td class="py-2.5 pr-4 text-ink-primary font-medium">
                    {p.name}
                    {#if p.is_leader}<Badge tone="amber" class="ml-1.5 text-[10px] px-1.5 py-0.5">Leader</Badge>{/if}
                  </td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.level || '?'}</td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.pal_count}</td>
                  <td class="py-2.5 pr-4"><Badge tone="accent">{p.guild_name ?? '—'}</Badge></td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.guild_level ?? '?'}</td>
                  <td class="py-2.5 pr-4 text-ink-secondary tabular-nums">{p.last_seen_text ?? 'Unknown'}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-muted max-w-[160px] truncate" title={p.uid}>{p.uid}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </Card>
  </div>
</SaveGate>

{#if selectedUid}
  <PlayerDetailModal
    uid={selectedUid}
    name={selectedName}
    onclose={closeDetail}
    onupdated={handleUpdated}
  />
{/if}
