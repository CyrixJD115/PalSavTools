<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded, t } from '$stores/index';
  import type { PlayerSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import PlayerDetailModal from '$components/players/PlayerDetailModal.svelte';
  import { infiniteScroll } from '$lib/utils/infiniteScroll';

  // Infinite-scroll state. Items accumulate as the user scrolls; the backend
  // returns 20 at a time and we trigger another fetch when the sentinel
  // approaches the viewport.
  const PAGE_SIZE = 20;
  let players = $state<PlayerSummary[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);

  // Debounced search — server-side filter. Resetting the list + scrolling
  // back to top happens whenever the query changes.
  let query = $state('');
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  let sortKey = $state<'name' | 'level' | 'pal_count' | 'last_seen' | 'guild_name'>('name');
  let sortAsc = $state(true);
  let selectedUid = $state<string | null>(null);
  let selectedName = $state('');

  const hasMore = $derived(players.length < total);

  async function fetchPage(reset = false) {
    if (reset) {
      loading = true;
      players = [];
    } else {
      if (loadingMore || !hasMore) return;
      loadingMore = true;
    }
    error = null;
    try {
      const offset = reset ? 0 : players.length;
      const res = await api.players({ limit: PAGE_SIZE, offset, search: query.trim() });
      total = res.total;
      // Dedup by UID (defensive — backend should already be unique).
      const seen = new Set(players.map((p) => p.uid));
      const next = reset ? res.players : [...players, ...res.players.filter((p) => !seen.has(p.uid))];
      players = next;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  async function loadMore() {
    await fetchPage(false);
  }

  function onSearchInput() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => fetchPage(true), 300);
  }

  onMount(() => {
    if ($saveLoaded) fetchPage(true);
  });

  // The server does the filtering now, so `sorted` just reorders the loaded
  // page locally. (Server can't sort without a sort param — local reorder
  // of the visible window is good enough for a typical page of 20.)
  const sorted = $derived(
    [...players].sort((a, b) => {
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
    fetchPage(true);
  }
</script>

<SaveGate icon="lucide:users">
  <div class="p-6 max-w-6xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.players.title')}</h1>
        <p class="text-xs text-ink-muted">{$t('web.players.count', { count: total })}</p>
      </div>
      <input
        class="input max-w-xs"
        placeholder={$t('web.players.filter_placeholder')}
        bind:value={query}
        oninput={onSearchInput}
      />
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
                  <span class="inline-flex items-center gap-1">{$t('web.players.col_name')}<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.name}>{arrows.name || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('level')}>
                  <span class="inline-flex items-center gap-1">{$t('web.players.col_level')}<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.level}>{arrows.level || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('pal_count')}>
                  <span class="inline-flex items-center gap-1">{$t('web.players.col_pals')}<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.pal_count}>{arrows.pal_count || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('guild_name')}>
                  <span class="inline-flex items-center gap-1">{$t('web.players.col_guild')}<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.guild_name}>{arrows.guild_name || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium select-none">{$t('web.players.col_guild_level')}</th>
                <th class="py-2 pr-4 font-medium cursor-pointer hover:text-ink-primary transition-fast select-none" onclick={() => toggleSort('last_seen')}>
                  <span class="inline-flex items-center gap-1">{$t('web.players.col_last_seen')}<span class="w-3 text-accent inline-block text-[10px]" class:invisible={!arrows.last_seen}>{arrows.last_seen || '▲'}</span></span>
                </th>
                <th class="py-2 pr-4 font-medium font-mono select-none">{$t('web.players.col_uid')}</th>
              </tr>
            </thead>
            <tbody use:infiniteScroll={{ onloadmore: loadMore, hasMore, loading: loadingMore }}>
              {#each sorted as p (p.uid)}
                <tr class="border-b border-line/20 hover:bg-bg-hover/50 transition-fast cursor-pointer" onclick={() => openDetail(p)}>
                  <td class="py-2.5 pr-4 text-ink-primary font-medium">
                    {p.name}
                    {#if p.is_leader}<Badge tone="amber" class="ml-1.5 text-[10px] px-1.5 py-0.5">{$t('web.players.leader_badge')}</Badge>{/if}
                  </td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.level || '?'}</td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.pal_count}</td>
                  <td class="py-2.5 pr-4"><Badge tone="accent">{p.guild_name ?? '—'}</Badge></td>
                  <td class="py-2.5 pr-4 tabular-nums">{p.guild_level ?? '?'}</td>
                  <td class="py-2.5 pr-4 text-ink-secondary tabular-nums">{p.last_seen_text ?? 'Unknown'}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-muted max-w-[160px] truncate" title={p.uid}>{p.uid}</td>
                </tr>
              {/each}
              <!-- sentinel: IntersectionObserver target for infinite scroll -->
              {#if hasMore}
                <tr class="sentinel">
                  <td colspan="7" class="py-3 text-center text-xs text-ink-muted">
                    {#if loadingMore}<Spinner size={14} />{:else}{$t('web.players.count', { count: total })}{/if}
                  </td>
                </tr>
              {/if}
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
