<script lang="ts">
  /**
   * MapSidebar — collapsible right-side panel with search, base/player lists,
   * and an info panel for the selected marker.
   *
   * Mirrors the PySide6 _sidebar_widget: search + QStackedWidget[base_tree |
   * player_tree] + info_label.
   */

  import Icon from '@iconify/svelte';
  import type { MapBase, MapPlayer } from '$types/index';
  import type { RuntimeMarker } from '$lib/map/types';
  import { sidebarOpen, mapSearch } from '$stores/mapStore';

  interface Props {
    bases: MapBase[];
    players: MapPlayer[];
    selectedMarker: RuntimeMarker | null;
    onSelectBase?: (b: MapBase) => void;
    onSelectPlayer?: (p: MapPlayer) => void;
    onZoomBase?: (b: MapBase) => void;
    onZoomPlayer?: (p: MapPlayer) => void;
  }

  let {
    bases,
    players,
    selectedMarker,
    onSelectBase,
    onSelectPlayer,
    onZoomBase,
    onZoomPlayer,
  }: Props = $props();

  let activeTab = $state<'bases' | 'players'>('bases');
  let expandedGuilds = $state<Set<string>>(new Set());

  // Group bases by guild
  let guildGroups = $derived.by(() => {
    const search = $mapSearch.toLowerCase().trim();
    const groups: { guildId: string; guildName: string; leaderName: string; lastSeen: string; bases: MapBase[] }[] = [];
    const map = new Map<string, { guildId: string; guildName: string; leaderName: string; lastSeen: string; bases: MapBase[] }>();

    for (const b of bases) {
      const gid = b.guild_id ?? 'unknown';
      if (!map.has(gid)) {
        const g = {
          guildId: gid,
          guildName: b.guild_name,
          leaderName: b.leader_name,
          lastSeen: '',
          bases: [] as MapBase[],
        };
        map.set(gid, g);
        groups.push(g);
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

  function toggleGuild(gid: string) {
    const next = new Set(expandedGuilds);
    if (next.has(gid)) next.delete(gid);
    else next.add(gid);
    expandedGuilds = next;
  }

  function handleBaseClick(b: MapBase) {
    onSelectBase?.(b);
  }

  function handlePlayerClick(p: MapPlayer) {
    onSelectPlayer?.(p);
  }

  function handleBaseDblClick(b: MapBase) {
    onZoomBase?.(b);
  }

  function handlePlayerDblClick(p: MapPlayer) {
    onZoomPlayer?.(p);
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
          placeholder="Search guilds, leaders, bases..."
          class="w-full pl-8 pr-2 py-1.5 text-xs bg-bg-elevated/60 border border-line/30 rounded-4
                 text-ink-primary placeholder:text-ink-dim focus:outline-none focus:border-accent-cyan/50"
          value={$mapSearch}
          oninput={(e) => mapSearch.set(e.currentTarget.value)}
        />
      </div>
      <button
        class={tabBtnBase + ' ' + (activeTab === 'bases' ? tabBtnActive : tabBtnInactive)}
        onclick={() => (activeTab = 'bases')}
      >
        Bases
      </button>
      <button
        class={tabBtnBase + ' ' + (activeTab === 'players' ? tabBtnActive : tabBtnInactive)}
        onclick={() => (activeTab = 'players')}
      >
        Players
      </button>
    </div>

    <!-- List area -->
    <div class="flex-1 overflow-y-auto overflow-x-hidden">
      {#if activeTab === 'bases'}
        <!-- Bases tree -->
        {#each guildGroups as g (g.guildId)}
          <div class="border-b border-line/5">
            <button
              class="flex items-center gap-1.5 w-full px-3 py-2 text-left hover:bg-bg-elevated/40 transition-colors"
              onclick={() => toggleGuild(g.guildId)}
            >
              <Icon
                icon={expandedGuilds.has(g.guildId) ? 'lucide:chevron-down' : 'lucide:chevron-right'}
                width="14"
                class="text-ink-dim shrink-0"
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
          <div class="px-3 py-8 text-center text-xs text-ink-dim">No bases found</div>
        {/each}
      {:else}
        <!-- Players list -->
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
                {#if p.level > 0}Lv {p.level} · {/if}{p.pal_count} pals
              </div>
            </div>
            <div class="text-[10px] text-ink-dim shrink-0">{p.last_seen_text ?? ''}</div>
          </button>
        {:else}
          <div class="px-3 py-8 text-center text-xs text-ink-dim">No players found</div>
        {/each}
      {/if}
    </div>

    <!-- Info panel -->
    <div class="border-t border-line/10 p-3 max-h-[40%] overflow-y-auto">
      {#if selectedMarker}
        {#if selectedMarker.kind === 'base'}
          {@const b = selectedMarker.data}
          <div class="space-y-1 text-[11px]">
            <div class="font-bold text-sm text-accent-cyan">{b.guild_name}</div>
            <div class="text-ink-muted">Level: <span class="text-ink-secondary">{b.guild_level}</span></div>
            <div class="text-ink-muted">Admin: <span class="text-ink-secondary">{b.leader_name}</span></div>
            <div class="text-ink-muted">Members: <span class="text-ink-secondary">{b.member_count}</span></div>
            <div class="text-ink-muted">Base Camps: <span class="text-ink-secondary">{b.base_position}/{b.total_bases}</span></div>
            <div class="text-ink-muted">Base ID: <span class="text-ink-secondary font-mono text-[10px]">{b.id}</span></div>
            <div class="text-ink-muted">Location: <span class="text-ink-secondary font-mono">X:{Math.round(selectedMarker.world_x)},Y:{Math.round(selectedMarker.world_y)}</span></div>
          </div>
        {:else}
          {@const p = selectedMarker.data}
          <div class="space-y-1 text-[11px]">
            <div class="font-bold text-sm text-emerald-400">{p.name}</div>
            <div class="text-ink-muted">UID: <span class="text-ink-secondary font-mono text-[10px]">{p.uid}</span></div>
            {#if p.level > 0}
              <div class="text-ink-muted">Level: <span class="text-ink-secondary">{p.level}</span></div>
            {/if}
            {#if p.guild_name}
              <div class="text-ink-muted">Guild: <span class="text-ink-secondary">{p.guild_name}</span></div>
            {/if}
            <div class="text-ink-muted">Pals: <span class="text-ink-secondary">{p.pal_count}</span></div>
            {#if p.last_seen_text}
              <div class="text-ink-muted">Last Seen: <span class="text-ink-secondary">{p.last_seen_text}</span></div>
            {/if}
            <div class="text-ink-muted">Location: <span class="text-ink-secondary font-mono">X:{Math.round(selectedMarker.world_x)},Y:{Math.round(selectedMarker.world_y)}</span></div>
          </div>
        {/if}
      {:else}
        <div class="text-xs text-ink-dim text-center py-2">
          Click on a marker or list item to view details
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
  title={$sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
>
  <Icon icon={$sidebarOpen ? 'lucide:chevron-right' : 'lucide:chevron-left'} width="16" />
</button>
