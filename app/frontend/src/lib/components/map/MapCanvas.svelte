<script lang="ts">
  /**
   * MapCanvas — the interactive canvas wrapper around MapEngine.
   *
   * Handles: pan (drag), zoom (wheel toward cursor), click/double-click/right-click,
   * hover tracking, resize, and the 60fps animation loop. Forwards semantic
   * events to the parent page via callback props.
   */

  import { onMount, onDestroy } from 'svelte';
  import { MapEngine } from './MapEngine';
  import { MAP_CONFIG } from '$lib/map/constants';
  import type { RuntimeMarker, Zone } from '$lib/map/types';

/** Extract the stable ID string from any marker type. */
function markerId(m: RuntimeMarker): string {
  if (m.kind === 'base') return m.data.id;
  if (m.kind === 'player') return m.data.uid;
  return (m.data as any).id;
}

  interface Props {
    onMarkerClick?: (m: RuntimeMarker) => void;
    onMarkerDoubleClick?: (m: RuntimeMarker) => void;
    onMarkerRightClick?: (m: RuntimeMarker, screenX: number, screenY: number) => void;
    onEmptyRightClick?: (screenX: number, screenY: number, imgX: number, imgY: number) => void;
    onZoneRightClick?: (z: Zone, screenX: number, screenY: number) => void;
    onHover?: (m: RuntimeMarker | null, screenX: number, screenY: number) => void;
    onCursorMove?: (worldX: number, worldY: number) => void;
    onZoomChange?: (zoom: number) => void;
  }

  let {
    onMarkerClick,
    onMarkerDoubleClick,
    onMarkerRightClick,
    onEmptyRightClick,
    onZoneRightClick,
    onHover,
    onCursorMove,
    onZoomChange,
  }: Props = $props();

  let canvasEl: HTMLCanvasElement;
  let engine: MapEngine;
  let rafId = 0;

  // Pan state
  let isPanning = false;
  let panStartX = 0;
  let panStartY = 0;
  let panOriginX = 0;
  let panOriginY = 0;
  let mouseDownX = 0;
  let mouseDownY = 0;
  let mouseDownButton = 0;
  let hasMoved = false;

  // Hover state
  let lastHoverScreenX = 0;
  let lastHoverScreenY = 0;

  function loop(now: number) {
    if (engine) {
      engine.tick(now);
      engine.render();
    }
    rafId = requestAnimationFrame(loop);
  }

  function getCanvasPos(e: MouseEvent): [number, number] {
    const rect = canvasEl.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  function handleMouseDown(e: MouseEvent) {
    const [sx, sy] = getCanvasPos(e);
    mouseDownX = sx;
    mouseDownY = sy;
    mouseDownButton = e.button;
    hasMoved = false;

    if (e.button === 0) {
      // Check if clicking a marker — if so, don't pan
      const hit = engine.hitTestMarker(sx, sy);
      if (!hit) {
        isPanning = true;
        panStartX = sx;
        panStartY = sy;
        panOriginX = engine.view.panX;
        panOriginY = engine.view.panY;
        canvasEl.style.cursor = 'grabbing';
      }
    }
  }

  function handleMouseMove(e: MouseEvent) {
    const [sx, sy] = getCanvasPos(e);
    lastHoverScreenX = sx;
    lastHoverScreenY = sy;

    if (isPanning) {
      const dx = sx - panStartX;
      const dy = sy - panStartY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasMoved = true;
      engine.view.panX = panOriginX + dx;
      engine.view.panY = panOriginY + dy;
    } else {
      // Hover detection
      const hit = engine.hitTestMarker(sx, sy);
      const prevHovered = engine.hoveredId;
      const prevKind = engine.hoveredKind;

      // Clear old hover
      for (const m of [...engine.baseMarkers, ...engine.playerMarkers, ...engine.poiMarkers]) {
        m.is_hovered = false;
      }

      if (hit) {
        engine.hoveredId = hit.kind === 'base' ? hit.data.id : hit.kind === 'player' ? hit.data.uid : (hit.data as any).id;
        engine.hoveredKind = hit.kind;
        hit.is_hovered = true;
        canvasEl.style.cursor = 'pointer';
      } else {
        const zHit = engine.hitTestZone(sx, sy);
        engine.hoveredId = null;
        engine.hoveredKind = null;
        engine.hoveredZoneId = zHit?.id ?? null;
        canvasEl.style.cursor = zHit ? 'pointer' : 'crosshair';
      }

      if (engine.hoveredId !== prevHovered || engine.hoveredKind !== prevKind) {
        const currentHit = hit || null;
        onHover?.(currentHit, sx, sy);
      } else if (hit) {
        onHover?.(hit, sx, sy);
      }

      // Cursor coords
      const [ix, iy] = engine.screenToImage(sx, sy);
      const [wx, wy] = engine.imageToWorld(ix, iy);
      onCursorMove?.(Math.round(wx), Math.round(wy));
    }

    // Update zone drawing preview point
    if (engine.zoneDrawing) {
      const [ix, iy] = engine.screenToImage(sx, sy);
      engine.previewPoint = { x: ix, y: iy };
    }
  }

  function handleMouseUp(e: MouseEvent) {
    const [sx, sy] = getCanvasPos(e);

    if (isPanning) {
      isPanning = false;
      canvasEl.style.cursor = 'crosshair';
    }

    // Click detection (no significant drag)
    if (!hasMoved && mouseDownButton === 0) {
      const hit = engine.hitTestMarker(sx, sy);
      if (hit) {
        onMarkerClick?.(hit);
      } else if (engine.zoneDrawing) {
        // Polygon point adding handled in double-click for start/close,
        // single-click adds intermediate points
        if (engine.zoneShape === 'polygon' && engine.polygonPoints.length >= 1) {
          const [ix, iy] = engine.screenToImage(sx, sy);
          engine.polygonPoints.push({ x: ix, y: iy });
        }
      }
    }
  }

  function handleDoubleClick(e: MouseEvent) {
    const [sx, sy] = getCanvasPos(e);
    const hit = engine.hitTestMarker(sx, sy);

    if (engine.zoneDrawing) {
      // Zone drawing actions
      const [ix, iy] = engine.screenToImage(sx, sy);
      if (engine.zoneShape === 'rect') {
        if (!engine.zonePointA) {
          engine.zonePointA = { x: ix, y: iy };
        } else {
          // Zone rect complete — pass real coords, not (0,0)
          onEmptyRightClick?.(sx, sy, ix, iy);
          engine.zonePointA = null;
        }
      } else {
        // Polygon: start or close
        if (engine.polygonPoints.length === 0) {
          engine.polygonPoints.push({ x: ix, y: iy });
        } else if (engine.polygonPoints.length >= 3) {
          // Polygon complete — pass real coords
          onEmptyRightClick?.(sx, sy, ix, iy);
        } else {
          engine.polygonPoints.push({ x: ix, y: iy });
        }
      }
      return;
    }

    if (hit) {
      // Zoom to marker
      engine.selectMarker(hit.kind, markerId(hit));
      engine.animateTo(hit.img_x, hit.img_y, MAP_CONFIG.zoom.double_click_target, 500);
      onMarkerDoubleClick?.(hit);
    }
  }

  function handleContextMenu(e: MouseEvent) {
    e.preventDefault();
    const [sx, sy] = getCanvasPos(e);

    const hit = engine.hitTestMarker(sx, sy);
    if (hit) {
      onMarkerRightClick?.(hit, e.clientX, e.clientY);
      return;
    }

    const zHit = engine.hitTestZone(sx, sy);
    if (zHit) {
      onZoneRightClick?.(zHit, e.clientX, e.clientY);
      return;
    }

    const [ix, iy] = engine.screenToImage(sx, sy);
    onEmptyRightClick?.(e.clientX, e.clientY, ix, iy);
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    const [sx, sy] = getCanvasPos(e);
    const factor = e.deltaY < 0 ? MAP_CONFIG.zoom.factor : 1 / MAP_CONFIG.zoom.factor;
    engine.zoomAt(sx, sy, factor);
    onZoomChange?.(engine.view.zoom);
  }

  function handleMouseLeave() {
    isPanning = false;
    for (const m of [...engine.baseMarkers, ...engine.playerMarkers]) {
      m.is_hovered = false;
    }
    engine.hoveredId = null;
    engine.hoveredKind = null;
    onHover?.(null, lastHoverScreenX, lastHoverScreenY);
    canvasEl.style.cursor = 'crosshair';
  }

  let resizeObserver: ResizeObserver | null = null;

  onMount(async () => {
    engine = new MapEngine(canvasEl);
    engine.callbacks = {
      onZoomChange: (z) => onZoomChange?.(z),
      onCursorMove: (wx, wy) => onCursorMove?.(wx, wy),
    };

    await engine.loadImages();

    const parent = canvasEl.parentElement!;
    const doResize = () => {
      engine.resize(parent.clientWidth, parent.clientHeight);
    };
    doResize();
    resizeObserver = new ResizeObserver(doResize);
    resizeObserver.observe(parent);

    // Initial render
    engine.render();
    rafId = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    if (rafId) cancelAnimationFrame(rafId);
    if (resizeObserver) resizeObserver.disconnect();
  });

  // Expose engine to parent
  export function getEngine(): MapEngine {
    return engine;
  }
</script>

<svelte:window on:contextmenu={(e) => { /* allow canvas to handle it */ }} />

<canvas
  bind:this={canvasEl}
  class="block w-full h-full"
  style="cursor: crosshair; touch-action: none;"
  onmousedown={handleMouseDown}
  onmousemove={handleMouseMove}
  onmouseup={handleMouseUp}
  ondblclick={handleDoubleClick}
  oncontextmenu={handleContextMenu}
  onwheel={handleWheel}
  onmouseleave={handleMouseLeave}
></canvas>
