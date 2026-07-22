<script lang="ts">
  /**
   * MapOverlay — top-right floating control bar + bottom HUD.
   * Mirrors the PySide6 overlay: Bases/Players/Rings/Zones/MapType toggles,
   * plus zoom controls and cursor/zoom readouts.
   */

  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import {
    showBases, showPlayers, showRings, showZones, mapType, zoom,
    showFastTravel, showDungeons, showBosses, showPredatorPals, showRelics,
    showPalIcons, sidebarOpen,
  } from '$stores/mapStore';

  interface Props {
    cursorWorld?: { x: number; y: number } | null;
    onZoomIn?: () => void;
    onZoomOut?: () => void;
    onResetView?: () => void;
  }

  let {
    cursorWorld = null,
    onZoomIn,
    onZoomOut,
    onResetView,
  }: Props = $props();

  let showPoiBar = $state(false);

  const btnClass =
    'flex items-center justify-center w-9 h-9 rounded-4 border transition-all duration-150 ' +
    'border-line/30 bg-bg-elevated/95 backdrop-blur text-ink-secondary hover:text-ink-primary ' +
    'hover:border-accent-cyan/50';

  const btnActiveClass =
    'flex items-center justify-center w-9 h-9 rounded-4 border transition-all duration-150 ' +
    'border-accent-cyan bg-bg-elevated/95 text-white';

  const poiBtnClass =
    'flex items-center gap-1.5 px-2.5 py-1 rounded-3 text-[10px] font-bold border transition-all duration-150 ' +
    'border-line/30 bg-bg-elevated/95 backdrop-blur text-ink-secondary hover:text-ink-primary ' +
    'hover:border-accent-cyan/50';

  const poiBtnActiveClass =
    'flex items-center gap-1.5 px-2.5 py-1 rounded-3 text-[10px] font-bold border transition-all duration-150 ' +
    'border-accent-cyan bg-bg-elevated/95 text-accent-cyan';

  const hudClass =
    'px-2 py-1 rounded-4 bg-bg-deep/90 backdrop-blur border border-line/30 ' +
    'text-[10px] font-mono text-ink-muted pointer-events-none';

  function toggleMapType() {
    mapType.update((t) => (t === 'world' ? 'tree' : 'world'));
  }
</script>

<!-- Top-left toolbar -->
<div class="absolute top-3 left-3 z-20 flex flex-col gap-1.5">
  <!-- Row 1: zoom + base layer toggles -->
  <div class="flex items-center gap-1.5">
    <button class={btnClass} title={$t('web.map.zoom_in')} onclick={() => onZoomIn?.()}>
      <Icon icon="lucide:zoom-in" width="18" />
    </button>
    <button class={btnClass} title={$t('web.map.zoom_out')} onclick={() => onZoomOut?.()}>
      <Icon icon="lucide:zoom-out" width="18" />
    </button>
    <button class={btnClass} title={$t('web.map.reset_view')} onclick={() => onResetView?.()}>
      <Icon icon="lucide:maximize" width="18" />
    </button>

    <div class="w-px h-7 bg-line/30 mx-0.5"></div>

    <button
      class={$showBases ? btnActiveClass : btnClass}
      title={$t('web.map.toggle_bases')}
      onclick={() => showBases.update((v) => !v)}
    >
      <Icon icon="lucide:home" width="18" />
    </button>
    <button
      class={$showPlayers ? btnActiveClass : btnClass}
      title={$t('web.map.toggle_players')}
      onclick={() => showPlayers.update((v) => !v)}
    >
      <Icon icon="lucide:user" width="18" />
    </button>
    <button
      class={$showRings ? btnActiveClass : btnClass}
      title={$t('web.map.toggle_rings')}
      onclick={() => showRings.update((v) => !v)}
    >
      <Icon icon="lucide:circle-dashed" width="18" />
    </button>
    <button
      class={$showZones ? btnActiveClass : btnClass}
      title={$t('web.map.toggle_zones')}
      onclick={() => showZones.update((v) => !v)}
    >
      <Icon icon="lucide:hexagon" width="18" />
    </button>

    <div class="w-px h-7 bg-line/30 mx-0.5"></div>

    <button
      class={$mapType === 'tree' ? btnActiveClass : btnClass}
      title={$mapType === 'world' ? $t('web.map.switch_tree') : $t('web.map.switch_world')}
      onclick={toggleMapType}
    >
      <Icon icon={$mapType === 'world' ? 'lucide:trees' : 'lucide:globe'} width="18" />
    </button>
  </div>

  <!-- Row 2: POI toggles (collapsible) -->
  <div class="flex items-center gap-1">
    <button
      class={showPoiBar ? btnActiveClass : btnClass}
      title={$t('web.map.toggle_poi_layers')}
      onclick={() => (showPoiBar = !showPoiBar)}
      style="width: 28px; height: 28px;"
    >
      <Icon icon="lucide:map-pin" width="14" />
    </button>

    {#if showPoiBar}
      <button
        class={$showFastTravel ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_fast_travel')}
        onclick={() => showFastTravel.update((v) => !v)}
      >
        <Icon icon="lucide:zap" width="12" /> {$t('web.map.poi_ft')}
      </button>
      <button
        class={$showDungeons ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_dungeons')}
        onclick={() => showDungeons.update((v) => !v)}
      >
        <Icon icon="lucide:landmark" width="12" /> {$t('web.map.poi_dungeon')}
      </button>
      <!-- Bosses: merged boss+alpha -->
      <button
        class={$showBosses ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_bosses')}
        onclick={() => showBosses.update((v) => !v)}
      >
        <Icon icon="lucide:skull" width="12" /> {$t('web.map.poi_boss')}
      </button>
      <button
        class={$showPredatorPals ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_predator_pals')}
        onclick={() => showPredatorPals.update((v) => !v)}
      >
        <Icon icon="lucide:bug" width="12" /> {$t('web.map.poi_predator')}
      </button>
      <button
        class={$showRelics ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_relics')}
        onclick={() => showRelics.update((v) => !v)}
      >
        <Icon icon="lucide:gem" width="12" /> {$t('web.map.poi_relic')}
      </button>
      <button
        class={$showPalIcons ? poiBtnActiveClass : poiBtnClass}
        title={$t('web.map.toggle_pal_icons')}
        onclick={() => showPalIcons.update((v) => !v)}
      >
        <Icon icon={$showPalIcons ? 'lucide:image' : 'lucide:image-off'} width="12" /> Pal Icon
      </button>
    {/if}
  </div>
</div>

<!-- Bottom-left cursor coords -->
<div class="absolute bottom-3 left-3 z-20 {hudClass}">
  {#if cursorWorld}
    {$t('web.map.cursor', { x: cursorWorld.x, y: cursorWorld.y })}
  {:else}
    {$t('web.map.cursor', { x: 0, y: 0 })}
  {/if}
</div>

<!-- Bottom-right zoom % — moves left when sidebar is open -->
<div class="absolute bottom-3 z-20 {hudClass}" style="right: {$sidebarOpen ? '348px' : '12px'};">
  {$t('web.map.zoom', { percent: Math.round($zoom * 100) })}
</div>
