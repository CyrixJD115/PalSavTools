<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded, t } from '$stores/index';
  import type { ContainerSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';
  import ContainerDetailModal from '$components/containers/ContainerDetailModal.svelte';

  let containers = $state<ContainerSummary[]>([]);
  let total = $state(0);
  let hasMore = $state(false);
  let loading = $state(true);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);
  let selectedContainer = $state<ContainerSummary | null>(null);
  let query = $state('');
  let sortCol = $state<'type' | 'slots' | 'items' | 'guild'>('type');
  let sortDir = $state<'asc' | 'desc'>('asc');
  let scrollTop = $state(0);
  let tableEl = $state<HTMLElement | null>(null);
  let sentinelEl = $state<HTMLElement | null>(null);

  const PAGE = 1000;
  let obs: IntersectionObserver | null = null;

  async function load() {
    loading = true; error = null; containers = [];
    try {
      const r = await api.containers(0, PAGE);
      containers = r.containers; total = r.total; hasMore = r.has_more;
    } catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    loadingMore = true;
    try {
      const r = await api.containers(containers.length, PAGE);
      containers = [...containers, ...r.containers];
      hasMore = r.has_more;
    } catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loadingMore = false; }
  }

  function setupObserver(el: HTMLElement) {
    sentinelEl = el;
    obs?.disconnect();
    obs = new IntersectionObserver(
      (entries) => { if (entries[0]?.isIntersecting) loadMore(); },
      { rootMargin: '200px' },
    );
    obs.observe(el);
  }

  onMount(() => { if ($saveLoaded) load(); });

  type SortCol = 'type' | 'slots' | 'items' | 'guild';
  function toggleSort(col: SortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
    load();
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

  /** Estimate visible row range from scroll position */
  const ROW_H = 37; // approximate row height in px
  let visibleRange = $derived.by(() => {
    if (!tableEl || filtered.length === 0 || containers.length === 0) return { from: 0, to: 0 };
    const scrollEl = tableEl.closest('.overflow-x-auto') ?? tableEl;
    const st = scrollEl instanceof HTMLElement ? scrollEl.scrollTop : 0;
    const ch = scrollEl instanceof HTMLElement ? scrollEl.clientHeight : 600;
    const first = Math.max(0, Math.floor(st / ROW_H));
    const last = Math.min(filtered.length, Math.ceil((st + ch) / ROW_H));
    return { from: first, to: Math.max(first + 1, last) };
  });

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

  function onDetailSaved() { selectedContainer = null; }

  function fmtVec(loc: [number, number, number] | null): string {
    if (!loc) return '—';
    if (loc[0] === 0 && loc[1] === 0 && loc[2] === 0) return '—';
    return `${loc[0].toFixed(0)}, ${loc[1].toFixed(0)}`;
  }

  function fmtRange(from: number, to: number, limit: number): string {
    const lo = Math.max(1, Math.min(from + 1, limit));
    const hi = Math.min(to, limit);
    if (lo >= hi) return `${limit.toLocaleString()}`;
    return `${lo.toLocaleString()}–${hi.toLocaleString()}`;
  }
</script>

<SaveGate icon="lucide:box">
  <div class="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.containers.title')}</h1>
        <p class="text-xs text-ink-muted">
          {#if loading}
            {$t('web.common.loading')}
          {:else}
            {$t('web.containers.count', { shown: containers.length.toLocaleString(), total: total.toLocaleString() })}
            {#if filtered.length !== containers.length}
              &middot; {$t('web.containers.filtered_shown', { count: filtered.length.toLocaleString() })}
            {/if}
            &middot; {$t('web.containers.row_range', { range: fmtRange(visibleRange.from, visibleRange.to, filtered.length) })}
          {/if}
        </p>
      </div>
      <input class="input max-w-xs" placeholder={$t('web.containers.filter_placeholder')} bind:value={query} />
    </div>

    <Card>
      {#if loading}
        <div class="flex justify-center py-12"><Spinner size={24} /></div>
      {:else if error}
        <p class="text-sm text-status-error p-4">{error}</p>
      {:else}
        <div class="overflow-x-auto" bind:this={tableEl} onscroll={() => scrollTop = tableEl?.scrollTop ?? 0}>
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-ink-muted border-b border-line/40">
                <th class="py-2 pr-4 font-medium cursor-pointer select-none hover:text-ink" onclick={() => toggleSort('type')}>
                  <span class="inline-flex items-center gap-1">
                    {$t('web.containers.col_type')}
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
                    {$t('web.containers.col_items')}
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
                    {$t('web.containers.col_slots')}
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
                    {$t('web.containers.col_guild')}
                    <span class="w-3 inline-flex justify-center">
                      {#if sortCol === 'guild'}
                        <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                      {:else}
                        <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                      {/if}
                    </span>
                  </span>
                </th>
                <th class="py-2 pr-4 font-medium">{$t('web.containers.col_location')}</th>
                <th class="py-2 pr-4 font-medium font-mono">{$t('web.containers.col_container_id')}</th>
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

        <!-- sentinel for infinite scroll -->
        {#if containers.length > 0}
          {#if hasMore}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="flex justify-center py-4"
              use:setupObserver
              role="status"
            >
              {#if loadingMore}
                <div class="flex items-center gap-2 text-xs text-ink-muted">
                  <Spinner size={16} />
                  {$t('web.containers.loading_more', { from: containers.length.toLocaleString(), to: Math.min(containers.length + PAGE, total).toLocaleString() })}
                </div>
              {:else}
                <span class="text-xs text-ink-dim">{$t('web.containers.scroll_for_more')}</span>
              {/if}
            </div>
          {:else}
            <p class="py-3 text-xs text-ink-dim text-center">{$t('web.containers.all_loaded', { count: total.toLocaleString() })}</p>
          {/if}
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
