<script lang="ts">
  /**
   * MapTooltip — floating hover card for base/player/POI markers.
   * Positioned near the cursor, styled to match the PySide6 hover overlays.
   */

  import type { RuntimeMarker } from '$lib/map/types';
  import { t } from '$stores/index';

  interface Props {
    marker: RuntimeMarker | null;
    x: number;
    y: number;
  }

  let { marker, x, y }: Props = $props();

  // Clamp position so tooltip stays within viewport
  let tooltipX = $derived(Math.min(x + 20, window.innerWidth - 280));
  let tooltipY = $derived(Math.max(y - 60, 10));

  /** POI kind → accent color. */
  function poiColor(kind: string): string {
    switch (kind) {
      case 'boss': return 'rgba(239,68,68,0.5)';
      case 'predator': return 'rgba(239,68,68,0.5)';
      case 'dungeon': return 'rgba(168,85,247,0.5)';
      case 'fast_travel': return 'rgba(34,211,238,0.5)';
      case 'relic': return 'rgba(52,211,153,0.5)';
      default: return 'rgba(255,255,255,0.3)';
    }
  }
</script>

{#if marker}
  <div
    class="absolute z-30 pointer-events-none max-w-[260px] rounded-8 border backdrop-blur-md shadow-xl transition-opacity duration-100"
    style="left: {tooltipX}px; top: {tooltipY}px; border-color: {marker.kind === 'base'
      ? 'rgba(0,255,200,0.4)'
      : marker.kind === 'player'
        ? 'rgba(0,255,150,0.4)'
        : poiColor(marker.kind)}; background: rgba(14,16,20,0.95);"
  >
    {#if marker.kind === 'base'}
      {@const b = marker.data}
      <div class="px-3 py-2 space-y-0.5 text-[11px]">
        <div class="font-bold text-sm text-accent-cyan truncate">{b.guild_name}</div>
        <div class="text-ink-muted">{$t('web.players.detail_level')} <span class="text-ink-secondary">{b.guild_level}</span></div>
        <div class="text-ink-muted">{$t('web.map.detail_admin')} <span class="text-ink-secondary">{b.leader_name}</span></div>
        <div class="text-ink-muted">{$t('web.common.members')}: <span class="text-ink-secondary">{b.member_count}</span></div>
        <div class="text-ink-muted">{$t('web.map.detail_base_camps')} <span class="text-ink-secondary">{b.base_position}/{b.total_bases}</span></div>
        <div class="text-ink-muted">{$t('web.bases.detail_base_id')} <span class="text-ink-secondary font-mono text-[10px]">{b.id.slice(0, 12)}...</span></div>
        <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(marker.world_x)},Y:{Math.round(marker.world_y)}</span></div>
      </div>
    {:else if marker.kind === 'player'}
      {@const p = marker.data}
      <div class="px-3 py-2 space-y-0.5 text-[11px]">
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
        <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(marker.world_x)},Y:{Math.round(marker.world_y)}</span></div>
      </div>
    {:else}
      <!-- POI marker tooltip -->
      {@const d = marker.data as any}
      <div class="px-3 py-2 space-y-0.5 text-[11px]">
        <div class="font-bold text-sm truncate" style="color: {poiColor(marker.kind)};">
          {d.name || marker.kind}
        </div>
        {#if marker.kind === 'boss'}
          <div class="text-ink-muted">{$t('web.players.detail_level')} <span class="text-ink-secondary">{d.level}</span></div>
        {:else if marker.kind === 'relic'}
          <div class="text-ink-muted">Type: <span class="text-ink-secondary">{d.relic_type}</span></div>
        {:else if marker.kind === 'predator' || marker.kind === 'boss'}
          <div class="text-ink-muted">{$t('web.map.poi_pal_name')} <span class="text-ink-secondary">{d.pal}</span></div>
        {/if}
        <div class="text-ink-muted">{$t('web.common.location')}: <span class="text-ink-secondary font-mono">X:{Math.round(marker.world_x)},Y:{Math.round(marker.world_y)}</span></div>
      </div>
    {/if}
  </div>
{/if}
