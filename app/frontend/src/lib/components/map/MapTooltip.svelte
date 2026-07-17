<script lang="ts">
  /**
   * MapTooltip — floating hover card for base/player markers.
   * Positioned near the cursor, styled to match the PySide6 BaseHoverOverlay /
   * PlayerHoverOverlay (dark glass card with colored accent border).
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
</script>

{#if marker}
  <div
    class="absolute z-30 pointer-events-none max-w-[260px] rounded-8 border backdrop-blur-md shadow-xl transition-opacity duration-100"
    style="left: {tooltipX}px; top: {tooltipY}px; {marker.kind === 'base'
      ? 'border-accent-cyan/40; background: rgba(14,16,20,0.95);'
      : 'border-emerald-400/50; background: rgba(14,16,20,0.95);'}"
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
    {:else}
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
    {/if}
  </div>
{/if}
