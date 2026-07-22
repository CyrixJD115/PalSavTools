<script lang="ts">
  /**
   * MapSidebar — collapsible right-side panel with search, base/player/POI lists,
   * and an info panel for the selected marker.
   */

  import Icon from '@iconify/svelte';
  import type { MapBase, MapPlayer, MapPoiResponse } from '$types/index';
  import type { RuntimeMarker, PoiKind } from '$lib/map/types';
  import { t } from '$stores/index';
  import { sidebarOpen, mapSearch, showRelics } from '$stores/mapStore';

  interface Props {
    bases: MapBase[];
    players: MapPlayer[];
    poiData: MapPoiResponse | null;
    selectedMarker: RuntimeMarker | null;
    /** Per-relic-type visibility toggle callback. */
    setRelicTypeVisibility?: (type: string, visible: boolean) => void;
    relicTypeVisibility?: Record<string, boolean>;

    onSelectBase?: (b: MapBase) => void;
    onSelectPlayer?: (p: MapPlayer) => void;
    onSelectPoi?: (kind: PoiKind, id: string) => void;
    onZoomBase?: (b: MapBase) => void;
    onZoomPlayer?: (p: MapPlayer) => void;
    onZoomPoi?: (kind: PoiKind, id: string) => void;
  }

  let {
    bases,
    players,
    poiData = null,
    selectedMarker,
    setRelicTypeVisibility,
    relicTypeVisibility = {},
    onSelectBase,
    onSelectPlayer,
    onSelectPoi,
    onZoomBase,
    onZoomPlayer,
    onZoomPoi,
  }: Props = $props();

  let activeTab = $state<'bases' | 'players' | 'pois'>('bases');
  let expandedGuilds = $state<Set<string>>(new Set());
  let expandedPoiTypes = $state<Set<PoiKind>>(new Set(['boss', 'dungeon', 'fast_travel']));

  // Group bases by guild
  let guildGroups = $derived.by(() => {
    const search = $mapSearch.toLowerCase().trim();
    const groups: { guildId: string; guildName: string; leaderName: string; lastSeen: string; bases: MapBase[] }[] = [];
    const map = new Map<string, { guildId: string; guildName: string; leaderName: string; lastSeen: string; bases: MapBase[] }>();

    for (const b of bases) {
      const gid = b.guild_id ?? 'unknown';
      if (!map.has(gid)) {
        map.set(gid, {
          guildId: gid,
          guildName: b.guild_name,
          leaderName: b.leader_name,
          lastSeen: '',
          bases: [] as MapBase[],
        });
        groups.push(map.get(gid)!);
      }
      map.get(gid)!.bases.push(b);
    }

    if (search) {
      const terms = search.split(/\s+/);
      return groups
        .map((g) => {
          const guildMatches = terms.every((t) =>
            g.guildName.toLowerCase().includes(t) || g.leaderName.toLowerCase().includes(t)
          );
          const matchingBases = g.bases.filter((b) =>
            terms.every((t) =>
              b.id.toLowerCase().includes(t) ||
              `${Math.round(b.world_img?.world_x ?? 0)}`.includes(t) ||
              `${Math.round(b.world_img?.world_y ?? 0)}`.includes(t) ||
              g.guildName.toLowerCase().includes(t) ||
              g.leaderName.toLowerCase().includes(t)
            )
          );
          if (guildMatches) return g;
          if (matchingBases.length > 0) return { ...g, bases: matchingBases };
          return null;
        })
        .filter((g): g is NonNullable<typeof g> => g !== null);
    }
    return groups;
  });

  let filteredPlayers = $derived.by(() => {
    const search = $mapSearch.toLowerCase().trim();
    if (!search) return players;
    const terms = search.split(/\s+/);
    return players.filter((p) =>
      terms.every((t) =>
        p.name.toLowerCase().includes(t) ||
        p.uid.toLowerCase().includes(t) ||
        (p.guild_name ?? '').toLowerCase().includes(t) ||
        (p.last_seen_text ?? '').toLowerCase().includes(t) ||
        `${Math.round(p.world_img?.world_x ?? 0)}`.includes(t) ||
        `${Math.round(p.world_img?.world_y ?? 0)}`.includes(t)
      )
    );
  });

  // POI data derived — groups with items for the sidebar
  const poiGroups = $derived.by(() => {
    const d = poiData;
    if (!d) return [];
    interface PoiGroup { kind: PoiKind; items: any[]; label: string }
    const groups: PoiGroup[] = [];
    // Boss + alpha (merged under "Bosses")
    const bossItems = d.entities.filter((e: any) => e.subtype === 'boss' || e.subtype === 'alpha');
    if (bossItems.length > 0) groups.push({ kind: 'boss', items: bossItems, label: 'Bosses' });
    // Predators
    const predItems = d.entities.filter((e: any) => e.subtype === 'predator');
    if (predItems.length > 0) groups.push({ kind: 'predator', items: predItems, label: 'Predators' });
    if (d.dungeons.length > 0) groups.push({ kind: 'dungeon', items: d.dungeons, label: 'Dungeons' });
    if (d.fast_travel.length > 0) groups.push({ kind: 'fast_travel', items: d.fast_travel, label: 'Fast Travel' });
    if (d.relics.length > 0) groups.push({ kind: 'relic', items: d.relics, label: 'Relics' });
    return groups;
  });

  const relicTypeData = $derived(
    poiData?.relic_data ? Object.entries(poiData.relic_data) as [string, any][] : []
  );

  function togglePoiType(kind: PoiKind) {
    const next = new Set(expandedPoiTypes);
    if (next.has(kind)) next.delete(kind);
    else next.add(kind);
    expandedPoiTypes = next;
  }

  function toggleGuild(gid: string) {
    const next = new Set(expandedGuilds);
    if (next.has(gid)) next.delete(gid);
    else next.add(gid);
    expandedGuilds = next;
  }

  function handleBaseClick(b: MapBase) { onSelectBase?.(b); }
  function handlePlayerClick(p: MapPlayer) { onSelectPlayer?.(p); }
  function handleBaseDblClick(b: MapBase) { onZoomBase?.(b); }
  function handlePlayerDblClick(p: MapPlayer) { onZoomPlayer?.(p); }

  /** Icons for each POI type. */
  function poiIcon(kind: PoiKind): string {
    switch (kind) {
      case 'boss': return 'lucide:skull';
      case 'predator': return 'lucide:bug';
      case 'dungeon': return 'lucide:landmark';
      case 'fast_travel': return 'lucide:zap';
      case 'relic': return 'lucide:gem';
    }
  }

  function poiColor(kind: PoiKind): string {
    switch (kind) {
      case 'boss': return 'text-red-400';
      case 'predator': return 'text-red-400';
      case 'dungeon': return 'text-purple-400';
      case 'fast_travel': return 'text-cyan-400';
      case 'relic': return 'text-emerald-400';
    }
  }

  function poiLabel(kind: PoiKind): string {
    switch (kind) {
      case 'boss': return 'Bosses';
      case 'predator': return $t('web.map.poi_predator');
      case 'dungeon': return $t('web.map.poi_dungeon');
      case 'fast_travel': return $t('web.map.poi_ft');
      case 'relic': return $t('web.map.poi_relic');
    }
  }

  const tabBtnBase =
    'px-3 py-1.5 text-xs font-bold rounded-6 border transition-all duration-150 cursor-pointer';
  const tabBtnActive = 'bg-accent-cyan/20 text-white border-accent-cyan/40';
  const tabBtnInactive =
    'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20 hover:bg-accent-cyan/20 hover:text-white';
</script>

{#if $sidebarOpen}
  <div class="absolute top-0 right-0 bottom-0 z-20 w-[340px] flex flex-col bg-bg-deep/95 backdrop-blur-md border-l border-line/20">
    <!-- Search + Tabs -->
    <div class="p-2.5 flex items-center gap-2 border-b border-line/10">
      <div class="relative flex-1">
        <Icon icon="lucide:search" width="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
        <input
          type="text"
          placeholder={$t('web.map.search_placeholder')}
          class="w-full pl-8 pr-2 py-1.5 text-xs bg-bg-elevated/60 border border-line/30 rounded-4
                 text-ink-primary placeholder:text-ink-dim focus:outline-none focus:border-accent-cyan/50"
          value={$mapSearch}
          oninput={(e) => mapSearch.set(e.currentTarget.value)}
        />
      </div>
      <button
        class={tabBtnBase + ' ' + (activeTab === 'bases' ? tabBtnActive : tabBtnInactive)}
        onclick={() => (activeTab = 'bases')}
      >{$t('web.map.tab_bases')}</button>
      <button
        class={tabBtnBase + ' ' + (activeTab === 'players' ? tabBtnActive : tabBtnInactive)}
        onclick={() => (activeTab = 'players')}
      >{$t('web.map.tab_players')}</button>
      {#if poiData}
        <button
          class={tabBtnBase + ' ' + (activeTab === 'pois' ? tabBtnActive : tabBtnInactive)}
          onclick={() => (activeTab = 'pois')}
        >POIs</button>
      {/if}
    </div>

    <!-- List area -->
    <div class="flex-1 overflow-y-auto overflow-x-hidden">
      {#if activeTab === 'bases'}
        {#each guildGroups as g (g.guildId)}
          <div class="border-b border-line/5">
            <button
              class="flex items-center gap-1.5 w-full px-3 py-2 text-left hover:bg-bg-elevated/40 transition-colors"
              onclick={() => toggleGuild(g.guildId)}
            >
              <Icon
                icon={expandedGuilds.has(g.guildId) ? 'lucide:chevron-down' : 'lucide:chevron-right'}
                width="14" class="text-ink-dim shrink-0"
              />
              <span class="text-xs font-bold text-accent-cyan truncate flex-1">{g.guildName}</span>
              <span class="text-[10px] text-ink-dim">{g.bases.length}</span>
            </button>
            {#if expandedGuilds.has(g.guildId)}
              <div class="pb-1">
                {#each g.bases as b (b.id)}
                  <button
                    class="flex items-center gap-2 w-full pl-8 pr-3 py-1.5 text-left hover:bg-bg-elevated/40
                           transition-colors {selectedMarker?.kind === 'base' && selectedMarker.data.id === b.id
                             ? 'bg-accent-cyan/10'
                             : ''}"
                    onclick={() => handleBaseClick(b)}
                    ondblclick={() => handleBaseDblClick(b)}
                  >
                    <Icon icon="lucide:map-pin" width="12" class="text-accent-cyan/60 shrink-0" />
                    <span class="text-[11px] text-ink-secondary font-mono">
                      X:{Math.round(b.world_img?.world_x ?? 0)} Y:{Math.round(b.world_img?.world_y ?? 0)}
                    </span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <div class="px-3 py-8 text-center text-xs text-ink-dim">{$t('web.map.no_bases')}</div>
        {/each}
      {:else if activeTab === 'players'}
        {#each filteredPlayers as p (p.uid)}
          <button
            class="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-bg-elevated/40 transition-colors
                   border-b border-line/5
                   {selectedMarker?.kind === 'player' && selectedMarker.data.uid === p.uid
                     ? 'bg-emerald-500/10'
                     : ''}"
            onclick={() => handlePlayerClick(p)}
            ondblclick={() => handlePlayerDblClick(p)}
          >
            <Icon icon="lucide:user" width="14" class="text-emerald-400/70 shrink-0" />
            <div class="flex-1 min-w-0">
              <div class="text-xs font-semibold text-emerald-400 truncate">{p.name}</div>
              <div class="text-[10px] text-ink-dim">
                {$t('web.map.lv_pals', { level: p.level, count: p.pal_count })}
              </div>
            </div>
            <div class="text-[10px] text-ink-dim shrink-0">{p.last_seen_text ?? ''}</div>
          </button>
        {:else}
          <div class="px-3 py-8 text-center text-xs text-ink-dim">{$t('web.map.no_players')}</div>
        {/each}
      {:else if activeTab === 'pois' && poiData}
        {#each poiGroups as group (group.kind)}
          {#if group.items.length > 0}
            <div class="border-b border-line/5">
              <button
                class="flex items-center gap-1.5 w-full px-3 py-2 text-left hover:bg-bg-elevated/40 transition-colors"
                onclick={() => togglePoiType(group.kind)}
              >
                <Icon
                  icon={expandedPoiTypes.has(group.kind) ? 'lucide:chevron-down' : 'lucide:chevron-right'}
                  width="14" class="text-ink-dim shrink-0"
                />
                <Icon icon={poiIcon(group.kind)} width="12" class={poiColor(group.kind) + ' shrink-0'} />
                <span class="text-xs font-bold text-ink-primary truncate flex-1">{poiLabel(group.kind)}</span>
                <span class="text-[10px] text-ink-dim">{group.items.length}</span>
              </button>
              {#if expandedPoiTypes.has(group.kind)}
                <div class="pb-1">
                  {#each group.items as poi, i}
                    <button
                      class="flex items-center gap-2 w-full pl-8 pr-3 py-1.5 text-left hover:bg-bg-elevated/40
                             transition-colors text-[11px] text-ink-secondary truncate"
                      onclick={() => onSelectPoi?.(group.kind, poi.id)}
                      ondblclick={() => onZoomPoi?.(group.kind, poi.id)}
                    >
                      {poi.name || poi.pal || poi.relic_type || `${group.kind} ${i + 1}`}
                    </button>
                  {/each}

                  <!-- Relic sub-type checkboxes -->
                  {#if group.kind === 'relic' && relicTypeData.length > 0}
                    <div class="pl-8 pr-3 pt-2 pb-1 space-y-1 border-t border-line/10 mt-1">
                      <div class="text-[10px] text-ink-dim mb-1">Filter by type:</div>
                      {#each relicTypeData as [type, info]}
                        <label class="flex items-center gap-1.5 py-0.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={relicTypeVisibility[type] !== false}
                            onchange={(e) => {
                              const v = (e.target as HTMLInputElement).checked;
                              setRelicTypeVisibility?.(type, v);
                            }}
                            class="accent-accent-cyan w-3 h-3"
                          />
                          <span class="text-[10px] text-ink-muted">{info?.localized_name || type}</span>
                          <span class="text-[9px] text-ink-dim ml-auto">{(info?.ranks?.length ?? 0)} ranks</span>
                        </label>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {/each}
      {/if}
    </div>

    <!-- Info panel -->
    <div class="border-t border-line/10 p-3 max-h-[40%] overflow-y-auto">
      {#if selectedMarker}
        {#if selectedMarker.kind === 'base'}
          {@const b = selectedMarker.data}
          <div class="space-y-1 text-[11px]">
            <div class="font-bold text-sm text-accent-cyan truncate">{b.guild_name}</div>
            <div class="text-ink-muted">{$t('web.players.detail_level')} <span class="text-ink-secondary">{b.guild_level}</span></div>
            <div class="text-ink-muted">{$t('web.map.detail_admin')} <span class="text-ink-secondary">{b.leader_name}</span></div>
            <div class="text-ink-muted">{$t('web.common.members')}: <span class="text-ink-secondary">{b.member_count}</span></div>
            <div class="text-ink-muted">{$t('web.map.detail_base_camps')} <span class="text-ink-secondary">{b.base_position}/{b.total_bases}</span></div>
            <div class="text-ink-muted">{$t('web.bases.detail_base_id')} <span class="text-ink-secondary font-mono text-[10px]">{b.id.slice(0, 12)}...</span></div>
            <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(selectedMarker.world_x)},Y:{Math.round(selectedMarker.world_y)}</span></div>
          </div>
        {:else if selectedMarker.kind === 'player'}
          {@const p = selectedMarker.data}
          <div class="space-y-1 text-[11px]">
            <div class="font-bold text-sm text-emerald-400 truncate">{p.name}</div>
            <div class="text-ink-muted">{$t('web.players.detail_uid')} <span class="text-ink-secondary font-mono text-[10px]">{p.uid.slice(0, 12)}...</span></div>
            {#if p.level > 0}
              <div class="text-ink-muted">{$t('web.players.detail_level')} <span class="text-ink-secondary">{p.level}</span></div>
            {/if}
            {#if p.guild_name}
              <div class="text-ink-muted">{$t('web.players.detail_guild')} <span class="text-ink-secondary">{p.guild_name}</span></div>
            {/if}
            <div class="text-ink-muted">{$t('web.map.detail_pals')} <span class="text-ink-secondary">{p.pal_count}</span></div>
            {#if p.last_seen_text}
              <div class="text-ink-muted">{$t('web.map.detail_last_seen')} <span class="text-ink-secondary">{p.last_seen_text}</span></div>
            {/if}
            <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(selectedMarker.world_x)},Y:{Math.round(selectedMarker.world_y)}</span></div>
          </div>
        {:else}
          <!-- POI info -->
          {@const d = selectedMarker.data as any}
          <div class="space-y-1 text-[11px]">
            <div class="font-bold text-sm truncate" style="color: {selectedMarker.kind === 'boss' ? '#f87171' : selectedMarker.kind === 'dungeon' ? '#a78bfa' : selectedMarker.kind === 'fast_travel' ? '#22d3ee' : selectedMarker.kind === 'alpha_pal' ? '#fbbf24' : selectedMarker.kind === 'predator_pal' ? '#f87171' : '#34d399'}">
              {d.name || d.pal || selectedMarker.kind}
            </div>
            {#if selectedMarker.kind === 'boss'}
              <div class="text-ink-muted">{$t('web.players.detail_level')} <span class="text-ink-secondary">{d.level}</span></div>
            {:else if selectedMarker.kind === 'relic'}
              <div class="text-ink-muted">Type: <span class="text-ink-secondary">{d.relic_type}</span></div>
            {/if}
            <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(selectedMarker.world_x)},Y:{Math.round(selectedMarker.world_y)}</span></div>
          </div>
        {/if}
      {:else}
        <div class="text-xs text-ink-dim text-center py-2">
          {$t('web.map.click_hint')}
        </div>
      {/if}
    </div>
  </div>
{/if}

<!-- Sidebar toggle button -->
<button
  class="absolute top-1/2 -translate-y-1/2 z-20 w-7 h-14 rounded-l-6 bg-bg-elevated/90 backdrop-blur border border-line/30
         border-r-0 flex items-center justify-center text-ink-muted hover:text-ink-primary hover:bg-bg-elevated
         transition-all"
  style="right: {$sidebarOpen ? '340px' : '0'}"
  onclick={() => sidebarOpen.update((v) => !v)}
  title={$sidebarOpen ? $t('web.map.hide_sidebar') : $t('web.map.show_sidebar')}
>
  <Icon icon={$sidebarOpen ? 'lucide:chevron-right' : 'lucide:chevron-left'} width="16" />
</button>
