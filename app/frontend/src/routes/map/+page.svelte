<script lang="ts">
  /**
   * Map page — full-bleed interactive Palworld world map.
   *
   * Composes MapCanvas (pan/zoom/render), MapOverlay (HUD toggles),
   * MapSidebar (search/lists/info), MapTooltip (hover cards), and
   * MapContextMenu (right-click actions).
   *
   * All coordinate math is done in the Python backend via /api/map/data;
   * the frontend receives pre-computed pixel coords and only does simple
   * pixel↔screen transforms for cursor display and zone drawing.
   */

  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import { saveLoaded, t } from '$stores/index';
  import { toast } from '$stores/toast';
  import {
    showBases, showPlayers, showRings, showZones, mapType, zoom,
    sidebarOpen, zoneDrawingMode, zoneShapeType, mapLoading, mapError,
  } from '$stores/mapStore';
  import {
    zones, add_rect_zone, add_polygon_zone, remove_zone, rename_zone,
    clear_all_zones, export_zones_json, import_zones_json,
  } from '$stores/zones';
  import { MAP_CONFIG } from '$lib/map/constants';
  import type { MapBase, MapPlayer, MapDataResponse } from '$types/index';
  import type { RuntimeMarker, Zone } from '$lib/map/types';

  import MapCanvas from '$components/map/MapCanvas.svelte';
  import MapOverlay from '$components/map/MapOverlay.svelte';
  import MapSidebar from '$components/map/MapSidebar.svelte';
  import MapTooltip from '$components/map/MapTooltip.svelte';
  import MapContextMenu from '$components/map/MapContextMenu.svelte';
  import type { MenuItem } from '$components/map/MapContextMenu.svelte';
  import Icon from '@iconify/svelte';
  import SaveGate from '$components/ui/SaveGate.svelte';

  let canvasRef = $state<MapCanvas | null>(null);
  let engine = $state.raw<import('$lib/components/map/MapEngine').MapEngine | null>(null);

  let bases = $state<MapBase[]>([]);
  let players = $state<MapPlayer[]>([]);
  let mapSize = $state(2048);
  let worldRange = $state(1000);
  let treeRange = $state(2500);

  // Tooltip state
  let tooltipMarker = $state<RuntimeMarker | null>(null);
  let tooltipX = $state(0);
  let tooltipY = $state(0);

  // Context menu state
  let contextMenuItems = $state<MenuItem[]>([]);
  let contextMenuX = $state(0);
  let contextMenuY = $state(0);
  let contextMenuOpen = $state(false);

  // Cursor coords
  let cursorWorld = $state<{ x: number; y: number } | null>(null);

  // Selected marker
  let selectedMarker = $state<RuntimeMarker | null>(null);

  // Zone drawing prompts
  let zonePromptText = $state('');

  async function loadData() {
    mapLoading.set(true);
    mapError.set(null);
    try {
      const data: MapDataResponse = await api.mapData();
      bases = data.bases;
      players = data.players;
      mapSize = data.map_size;
      worldRange = data.world_coord_range;
      treeRange = data.tree_coord_range;
      if (engine) {
        engine.setMapData(bases, players, mapSize, worldRange, treeRange);
        engine.zones = $zones;
      }
    } catch (e) {
      mapError.set(e instanceof Error ? e.message : $t('web.map.load_failed'));
    } finally {
      mapLoading.set(false);
    }
  }

  onMount(() => {
    if ($saveLoaded) loadData();
  });

  // Clean up references on tab switch so GC can collect promptly.
  onDestroy(() => {
    bases = [];
    players = [];
    engine = null;
    canvasRef = null;
    mapLoading.set(false);
    mapError.set(null);
  });

  // React to save loaded changes
  $effect(() => {
    if ($saveLoaded && engine) {
      loadData();
    }
  });

  // Get engine reference once canvas is mounted
  $effect(() => {
    if (canvasRef) {
      engine = canvasRef.getEngine();
      if (bases.length > 0) {
        engine.setMapData(bases, players, mapSize, worldRange, treeRange);
        engine.zones = $zones;
      }
    }
  });

  // Sync store toggles to engine
  $effect(() => {
    if (engine) {
      engine.showBases = $showBases;
      engine.showPlayers = $showPlayers;
      engine.showRings = $showRings;
      engine.showZones = $showZones;
    }
  });

  // Sync zones store to engine
  $effect(() => {
    if (engine) {
      engine.zones = $zones;
    }
  });

  // Sync map type
  $effect(() => {
    if (engine) {
      engine.setMapType($mapType);
    }
  });

  // ---- event handlers ------------------------------------------------------

  function handleMarkerClick(m: RuntimeMarker) {
    if (!engine) return;
    selectedMarker = m;
    engine.selectMarker(m.kind, m.kind === 'base' ? m.data.id : m.data.uid);
  }

  function handleMarkerDoubleClick(m: RuntimeMarker) {
    if (!engine) return;
    selectedMarker = m;
    engine.selectMarker(m.kind, m.kind === 'base' ? m.data.id : m.data.uid);
  }

  function handleMarkerRightClick(m: RuntimeMarker, sx: number, sy: number) {
    if (!engine) return;
    selectedMarker = m;
    engine.selectMarker(m.kind, m.kind === 'base' ? m.data.id : m.data.uid);

    if (m.kind === 'base') {
      contextMenuItems = [
        { label: $t('web.map.ctx_delete_base'), icon: 'lucide:trash-2', danger: true, action: () => deleteBase(m) },
        { label: $t('web.map.ctx_export_base'), icon: 'lucide:download', action: () => exportBase(m) },
        { label: $t('web.map.ctx_adjust_radius'), icon: 'lucide:circle-dashed', action: () => adjustRadius(m) },
      ];
    } else {
      contextMenuItems = [
        { label: $t('web.map.ctx_delete_player'), icon: 'lucide:trash-2', danger: true, action: () => deletePlayer(m) },
        { label: $t('web.map.ctx_rename_player'), icon: 'lucide:pencil', action: () => renamePlayer(m) },
        { label: $t('web.map.ctx_unlock_cage'), icon: 'lucide:unlock', action: () => unlockCage(m) },
        { label: $t('web.map.ctx_unlock_techs'), icon: 'lucide:sparkles', action: () => unlockTech(m) },
      ];
    }
    contextMenuX = sx;
    contextMenuY = sy;
    contextMenuOpen = true;
  }

  function handleEmptyRightClick(sx: number, sy: number, imgX: number, imgY: number) {
    if (!engine) return;
    // If zone drawing mode, create zone from current points
    if (engine.zoneDrawing) {
      finishZoneDrawing();
      return;
    }

    contextMenuItems = [
      { label: $t('web.map.ctx_draw_zones'), icon: 'lucide:hexagon', action: startZoneDrawing },
      { label: $t('web.map.ctx_clear_zones'), icon: 'lucide:eraser', danger: true, action: () => {
        clear_all_zones();
        toast.success($t('web.toast.all_zones_cleared'));
      }},
      { label: '', action: () => {}, separator: true },
      { label: $t('web.map.ctx_export_zones'), icon: 'lucide:download', action: exportZones },
      { label: $t('web.map.ctx_import_zones'), icon: 'lucide:upload', action: importZones },
    ];
    contextMenuX = sx;
    contextMenuY = sy;
    contextMenuOpen = true;
  }

  function handleZoneRightClick(z: Zone, sx: number, sy: number) {
    contextMenuItems = [
      { label: $t('web.map.ctx_delete_zone', { name: z.name }), icon: 'lucide:trash-2', danger: true, action: () => {
        remove_zone(z.id);
        toast.success($t('web.toast.zone_deleted', { name: z.name }));
      }},
      { label: $t('web.map.ctx_rename_zone'), icon: 'lucide:pencil', action: () => {
        const name = window.prompt($t('web.map.zone_name_prompt'), z.name);
        if (name && name.trim()) {
          rename_zone(z.id, name.trim());
          toast.success($t('web.toast.zone_renamed'));
        }
      }},
    ];
    contextMenuX = sx;
    contextMenuY = sy;
    contextMenuOpen = true;
  }

  function handleHover(m: RuntimeMarker | null, sx: number, sy: number) {
    tooltipMarker = m;
    tooltipX = sx;
    tooltipY = sy;
  }

  function handleCursorMove(wx: number, wy: number) {
    cursorWorld = { x: wx, y: wy };
  }

  function handleZoomChange(z: number) {
    zoom.set(z);
  }

  // ---- sidebar actions ------------------------------------------------------

  function handleSelectBase(b: MapBase) {
    if (!engine) return;
    const marker = engine.baseMarkers.find((m) => m.data.id === b.id);
    if (marker) {
      selectedMarker = marker;
      engine.selectMarker('base', b.id);
    }
  }

  function handleSelectPlayer(p: MapPlayer) {
    if (!engine) return;
    const marker = engine.playerMarkers.find((m) => m.data.uid === p.uid);
    if (marker) {
      selectedMarker = marker;
      engine.selectMarker('player', p.uid);
    }
  }

  function handleZoomBase(b: MapBase) {
    if (!engine) return;
    const marker = engine.baseMarkers.find((m) => m.data.id === b.id);
    if (marker) {
      selectedMarker = marker;
      engine.selectMarker('base', b.id);
      engine.animateTo(marker.img_x, marker.img_y, MAP_CONFIG.zoom.double_click_target);
    }
  }

  function handleZoomPlayer(p: MapPlayer) {
    if (!engine) return;
    const marker = engine.playerMarkers.find((m) => m.data.uid === p.uid);
    if (marker) {
      selectedMarker = marker;
      engine.selectMarker('player', p.uid);
      engine.animateTo(marker.img_x, marker.img_y, MAP_CONFIG.zoom.double_click_target);
    }
  }

  // ---- zone drawing ---------------------------------------------------------

  function startZoneDrawing() {
    zoneDrawingMode.set(true);
    zoneShapeType.set('rect');
    if (engine) {
      engine.zoneDrawing = true;
      engine.zoneShape = 'rect';
      engine.zonePointA = null;
      engine.polygonPoints = [];
    }
    showZones.set(true);
    zonePromptText = $t('web.map.zone_line_hint');
  }

  function finishZoneDrawing() {
    if (!engine) return;
    const eng = engine;
    if (eng.zoneShape === 'rect' && eng.zonePointA && eng.previewPoint) {
      const [wx1, wy1] = eng.imageToWorld(eng.zonePointA.x, eng.zonePointA.y);
      const [wx2, wy2] = eng.imageToWorld(eng.previewPoint.x, eng.previewPoint.y);
      add_rect_zone(wx1, wy1, wx2, wy2);
      toast.success($t('web.toast.zone_created'));
    } else if (eng.zoneShape === 'polygon' && eng.polygonPoints.length >= 3) {
      const worldPoints = eng.polygonPoints.map((p) => {
        const [wx, wy] = eng.imageToWorld(p.x, p.y);
        return { x: wx, y: wy };
      });
      add_polygon_zone(worldPoints);
      toast.success($t('web.toast.polygon_created'));
    }
    // Reset for next zone (stay in drawing mode like PySide6)
    engine.zonePointA = null;
    engine.polygonPoints = [];
  }

  function stopZoneDrawing() {
    zoneDrawingMode.set(false);
    if (engine) {
      engine.zoneDrawing = false;
      engine.zonePointA = null;
      engine.polygonPoints = [];
      engine.previewPoint = null;
    }
    zonePromptText = '';
  }

  // ---- zone import/export ---------------------------------------------------

  function exportZones() {
    const json = export_zones_json();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'protection_zones.json';
    a.click();
    URL.revokeObjectURL(url);
    toast.success($t('web.toast.zones_exported'));
  }

  function importZones() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = () => {
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        if (import_zones_json(reader.result as string)) {
          toast.success($t('web.toast.zones_imported'));
        } else {
          toast.error($t('web.toast.import_zones_invalid'));
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }

  // ---- placeholder actions (backend endpoints needed for Phase 11) ---------

  async function deleteBase(m: RuntimeMarker) {
    if (m.kind !== 'base') return;
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_delete_base') }));
  }

  async function exportBase(m: RuntimeMarker) {
    if (m.kind !== 'base') return;
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_export_base') }));
  }

  async function adjustRadius(m: RuntimeMarker) {
    if (m.kind !== 'base') return;
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_adjust_radius') }));
  }

  async function deletePlayer(m: RuntimeMarker) {
    if (m.kind !== 'player') return;
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_delete_player') }));
  }

  async function renamePlayer(m: RuntimeMarker) {
    if (m.kind !== 'player') return;
    const name = window.prompt($t('web.map.player_name_prompt'), m.data.name);
    if (name && name.trim()) {
      toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_rename_player') }));
    }
  }

  async function unlockCage(m: RuntimeMarker) {
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_unlock_cage') }));
  }

  async function unlockTech(m: RuntimeMarker) {
    toast.info($t('web.toast.feature_coming_soon', { feature: $t('web.toast.feature_unlock_techs') }));
  }

  // ESC to cancel zone drawing
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && $zoneDrawingMode) {
      stopZoneDrawing();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<SaveGate icon="lucide:map">
  <div class="fixed inset-0 -z-10"></div>
  <div class="relative w-full h-[calc(100vh-57px)] overflow-hidden bg-bg-deep">
    <!-- Canvas -->
    <MapCanvas
      bind:this={canvasRef}
      onMarkerClick={handleMarkerClick}
      onMarkerDoubleClick={handleMarkerDoubleClick}
      onMarkerRightClick={handleMarkerRightClick}
      onEmptyRightClick={handleEmptyRightClick}
      onZoneRightClick={handleZoneRightClick}
      onHover={handleHover}
      onCursorMove={handleCursorMove}
      onZoomChange={handleZoomChange}
    />

    <!-- Overlay HUD -->
    <MapOverlay
      {cursorWorld}
      onZoomIn={() => engine?.zoomBy(MAP_CONFIG.zoom.factor)}
      onZoomOut={() => engine?.zoomBy(1 / MAP_CONFIG.zoom.factor)}
      onResetView={() => engine?.resetView()}
    />

    <!-- Sidebar -->
    <MapSidebar
      {bases}
      {players}
      {selectedMarker}
      onSelectBase={handleSelectBase}
      onSelectPlayer={handleSelectPlayer}
      onZoomBase={handleZoomBase}
      onZoomPlayer={handleZoomPlayer}
    />

    <!-- Tooltip -->
    <MapTooltip marker={tooltipMarker} x={tooltipX} y={tooltipY} />

    <!-- Context Menu -->
    {#if contextMenuOpen}
      <MapContextMenu
        items={contextMenuItems}
        x={contextMenuX}
        y={contextMenuY}
        onclose={() => (contextMenuOpen = false)}
      />
    {/if}

    <!-- Zone drawing prompt bar -->
    {#if $zoneDrawingMode}
      <div class="absolute top-3 left-1/2 -translate-x-1/2 z-20 px-4 py-2 rounded-6 bg-bg-elevated/95
                  backdrop-blur border border-accent-cyan/30 text-xs text-accent-cyan flex items-center gap-3">
        <Icon icon="lucide:hexagon" width="14" />
        <span>{zonePromptText}</span>
        <!-- Shape selector -->
        <div class="flex items-center gap-1 ml-2">
          <button
            class="px-2 py-0.5 rounded-3 text-[10px] font-bold border transition-colors
                   {$zoneShapeType === 'rect'
                     ? 'bg-accent-cyan/30 border-accent-cyan text-white'
                     : 'bg-transparent border-line/30 text-ink-muted hover:text-ink-primary'}"
            onclick={() => {
              zoneShapeType.set('rect');
              if (engine) {
                engine.zoneShape = 'rect';
                engine.zonePointA = null;
                engine.polygonPoints = [];
              }
            }}
          >
            {$t('web.map.shape_rect')}
          </button>
          <button
            class="px-2 py-0.5 rounded-3 text-[10px] font-bold border transition-colors
                   {$zoneShapeType === 'polygon'
                     ? 'bg-accent-cyan/30 border-accent-cyan text-white'
                     : 'bg-transparent border-line/30 text-ink-muted hover:text-ink-primary'}"
            onclick={() => {
              zoneShapeType.set('polygon');
              if (engine) {
                engine.zoneShape = 'polygon';
                engine.zonePointA = null;
                engine.polygonPoints = [];
              }
              zonePromptText = $t('web.map.zone_polygon_hint');
            }}
          >
            {$t('web.map.shape_polygon')}
          </button>
        </div>
        <button
          class="ml-2 px-2 py-0.5 rounded-3 text-[10px] font-bold bg-red-500/20 border border-red-500/40
                 text-red-400 hover:bg-red-500/30"
          onclick={stopZoneDrawing}
        >
          {$t('web.map.stop')}
        </button>
      </div>
    {/if}

    <!-- Loading overlay -->
    {#if $mapLoading}
      <div class="absolute inset-0 z-40 flex items-center justify-center bg-bg-deep/80 backdrop-blur">
        <div class="text-center">
          <div class="animate-spin w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full mx-auto mb-3"></div>
          <div class="text-xs text-ink-muted">{$t('web.map.loading_data')}</div>
        </div>
      </div>
    {/if}
  </div>
</SaveGate>

<style>
  :global(body) {
    overflow: hidden;
  }
</style>
