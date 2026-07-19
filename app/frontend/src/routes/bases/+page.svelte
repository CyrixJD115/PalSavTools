<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded, t } from '$stores/index';
  import type { BaseSummary } from '$types/index';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';
  import BaseDetailModal from '$components/bases/BaseDetailModal.svelte';
  import { infiniteScroll } from '$lib/utils/infiniteScroll';

  const PAGE_SIZE = 20;
  let bases = $state<BaseSummary[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);
  let selectedBase = $state<BaseSummary | null>(null);
  let sortCol = $state<'name' | 'level' | 'members' | 'bases' | 'area'>('name');
  let sortDir = $state<'asc' | 'desc'>('asc');
  let query = $state('');
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  const hasMore = $derived(bases.length < total);

  async function fetchPage(reset = false) {
    if (reset) {
      loading = true;
      bases = [];
    } else {
      if (loadingMore || !hasMore) return;
      loadingMore = true;
    }
    error = null;
    try {
      const offset = reset ? 0 : bases.length;
      const res = await api.bases({ limit: PAGE_SIZE, offset, search: query.trim() });
      total = res.total;
      const seen = new Set(bases.map((b) => b.id));
      bases = reset ? res.bases : [...bases, ...res.bases.filter((b) => !seen.has(b.id))];
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  async function loadMore() { await fetchPage(false); }

  function onSearchInput() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => fetchPage(true), 300);
  }

  onMount(() => { if ($saveLoaded) fetchPage(true); });

  function fmtCoord(loc: [number, number, number] | null): string {
    if (!loc) return '—';
    return `${loc[0].toFixed(0)}, ${loc[1].toFixed(0)}, ${loc[2].toFixed(0)}`;
  }

  type SortCol = 'name' | 'level' | 'members' | 'bases' | 'area';
  let sortConfigs: { col: SortCol; labelKey: string; icon: string; css: string }[] = [
    { col: 'name', labelKey: 'web.bases.col_guild', icon: 'lucide:building-2', css: '' },
    { col: 'level', labelKey: 'web.bases.col_guild_lv', icon: 'lucide:arrow-up', css: 'text-right' },
    { col: 'members', labelKey: 'web.bases.col_members', icon: 'lucide:users', css: 'text-right' },
    { col: 'bases', labelKey: 'web.bases.col_bases', icon: 'lucide:map-pin', css: 'text-right' },
    { col: 'area', labelKey: 'web.bases.col_area_range', icon: 'lucide:maximize-2', css: 'text-right' },
  ];

  function toggleSort(col: SortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
  }

  let sorted = $derived([...bases].sort((a, b) => {
    let cmp = 0;
    if (sortCol === 'name') cmp = (a.guild_name ?? '').localeCompare(b.guild_name ?? '');
    else if (sortCol === 'level') cmp = (a.guild_level ?? 0) - (b.guild_level ?? 0);
    else if (sortCol === 'members') cmp = a.member_count - b.member_count;
    else if (sortCol === 'bases') cmp = a.total_bases - b.total_bases;
    else if (sortCol === 'area') cmp = a.area_range - b.area_range;
    return sortDir === 'asc' ? cmp : -cmp;
  }));

  function onDetailSaved() { fetchPage(true); selectedBase = null; }
</script>

<SaveGate icon="lucide:map-pin">
  <div class="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.bases.title')}</h1>
        <p class="text-xs text-ink-muted">{$t('web.bases.count', { count: total })}</p>
      </div>
      <input
        class="input max-w-xs"
        placeholder={$t('web.bases.filter_placeholder', { default: 'Search bases…' })}
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
                {#each sortConfigs as cfg}
                  <th
                    class="py-2 pr-4 font-medium {cfg.css} cursor-pointer select-none hover:text-ink"
                    onclick={() => toggleSort(cfg.col)}
                  >
                    <span class="inline-flex items-center gap-1">
                      {$t(cfg.labelKey)}
                      <span class="w-3 inline-flex justify-center">
                        {#if sortCol === cfg.col}
                          <Icon icon={sortDir === 'asc' ? 'lucide:arrow-up' : 'lucide:arrow-down'} width={11} />
                        {:else}
                          <span class="invisible"><Icon icon="lucide:arrow-up" width={11} /></span>
                        {/if}
                      </span>
                    </span>
                  </th>
                {/each}
                <th class="py-2 pr-4 font-medium">{$t('web.bases.col_location')}</th>
                <th class="py-2 pr-4 font-medium font-mono">{$t('web.bases.col_base_id')}</th>
              </tr>
            </thead>
            <tbody use:infiniteScroll={{ onloadmore: loadMore, hasMore, loading: loadingMore }}>
              {#each sorted as b (b.id)}
                <tr
                  class="border-b border-line/20 hover:bg-bg-hover/50 transition-fast cursor-pointer"
                  onclick={() => selectedBase = b}
                >
                  <td class="py-2.5 pr-4">
                    <span class="inline-flex items-center gap-1.5">
                      <Icon icon="lucide:building-2" width={13} class="text-ink-dim shrink-0" />
                      {#if b.guild_name}
                        {b.guild_name}
                      {:else}
                        <span class="text-ink-dim">—</span>
                      {/if}
                      {#if b.base_position === 1}
                        <Badge tone="amber">{$t('web.bases.main_badge')}</Badge>
                      {/if}
                    </span>
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">{b.guild_level ?? '—'}</td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">{b.member_count}</td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">{b.base_position}/{b.total_bases}</td>
                  <td class="py-2.5 pr-4 text-right tabular-nums font-mono text-xs">{(b.area_range / 100).toFixed(0)}m</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-secondary tabular-nums">{fmtCoord(b.location)}</td>
                  <td class="py-2.5 pr-4 font-mono text-xs text-ink-muted">{b.id.slice(0, 13)}…</td>
                </tr>
              {/each}
              {#if hasMore}
                <tr class="sentinel">
                  <td colspan="7" class="py-3 text-center text-xs text-ink-muted">
                    {#if loadingMore}<Spinner size={14} />{:else}{$t('web.bases.count', { count: total })}{/if}
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

{#if selectedBase}
  <BaseDetailModal
    base={selectedBase}
    onclose={() => selectedBase = null}
    onsaved={onDetailSaved}
  />
{/if}
