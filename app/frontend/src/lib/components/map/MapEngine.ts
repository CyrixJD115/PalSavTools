/**
 * MapEngine — the core canvas rendering engine for the Palworld map.
 *
 * Manages:
 *  - View state (pan, zoom, baseScale) and screen↔image coordinate transforms
 *  - Background image rendering (T_WorldMap.webp / T_TreeMap.webp)
 *  - Marker rendering (base/player icons, glow, shine sweep, dynamic sizing)
 *  - Radius rings (cyan translucent circles in image space)
 *  - Exclusion zones (red translucent rect/polygon in image space)
 *  - Effects (delete/import/export particle animations)
 *  - Zone drawing preview
 *  - Hit testing
 *  - Smooth zoom-to-marker animation
 *
 * The engine is framework-agnostic. The owning Svelte component calls
 * `attach()`, feeds it data, and triggers `render()` / `tick()`.
 */

import {
  MAP_CONFIG, PLAYER_MARKER, MAP_BG_COLOR, MAP_ASSETS, MAP_SCALE,
  area_range_to_image_px,
} from '$lib/map/constants';
import type {
  RuntimeBaseMarker, RuntimePlayerMarker, RuntimePoiMarker, RuntimeMarker,
  Zone, MapEffect, PoiKind,
} from '$lib/map/types';
import type { MapBase, MapPlayer, MapType, MapPoiResponse } from '$types/index';

// ---- view state -----------------------------------------------------------

export interface ViewState {
  panX: number;
  panY: number;
  zoom: number;   // user zoom factor (1.0 = fit, up to 30.0)
  baseScale: number; // scale to fit image in canvas
}

export interface EngineCallbacks {
  onZoomChange?: (zoom: number) => void;
  onCursorMove?: (worldX: number, worldY: number) => void;
  onMarkerHover?: (marker: RuntimeMarker | null) => void;
  onMarkerSelect?: (marker: RuntimeMarker | null) => void;
  onZoneHover?: (zone: Zone | null) => void;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load ${src}`));
    img.src = src;
  });
}

// ---- effect helpers (particle drawing) ------------------------------------

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export class MapEngine {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  mapSize: number;
  worldCoordRange: number;
  treeCoordRange: number;

  view: ViewState = { panX: 0, panY: 0, zoom: 1.0, baseScale: 1.0 };
  mapType: MapType = 'world';

  private bgWorld: HTMLImageElement | null = null;
  private bgTree: HTMLImageElement | null = null;
  private baseIcon: HTMLImageElement | null = null;
  private playerIcon: HTMLImageElement | null = null;
  private bossIcon: HTMLImageElement | null = null;
  private dungeonIcon: HTMLImageElement | null = null;
  private fastTravelIcon: HTMLImageElement | null = null;
  private relicGenericIcon: HTMLImageElement | null = null;
  /** Lazy-loaded pal portrait cache (alpha/predator pals). Null = failed load. */
  private palPortraitCache = new Map<string, HTMLImageElement | null>();
  /** Lazy-loaded relic per-type icon cache. */
  private relicIconCache = new Map<string, HTMLImageElement>();
  private imagesLoaded = false;

  baseMarkers: RuntimeBaseMarker[] = [];
  playerMarkers: RuntimePlayerMarker[] = [];
  poiMarkers: RuntimePoiMarker[] = [];
  zones: Zone[] = [];
  effects: MapEffect[] = [];

  showBases = true;
  showPlayers = false;
  showRings = true;
  showZones = false;

  // POI layer visibility
  showFastTravel = true;
  showDungeons = true;
  /** Shows boss + alpha entities. */
  showBosses = false;
  /** Shows predator entities (red-border portrait). */
  showPredatorPals = false;
  showRelics = true;
  /** Per-relic-type visibility; a missing key means visible. */
  relicTypeVisibility: Record<string, boolean> = {};
  /** When true, boss/alpha/predator entities render their pal portrait instead of generic icon. */
  showPalIcons = false;

  selectedId: string | null = null;
  selectedKind: 'base' | 'player' | PoiKind | null = null;
  hoveredId: string | null = null;
  hoveredKind: 'base' | 'player' | null = null;
  hoveredZoneId: string | null = null;

  // Zone drawing state
  zoneDrawing = false;
  zoneShape: 'rect' | 'polygon' = 'rect';
  zonePointA: { x: number; y: number } | null = null;
  polygonPoints: { x: number; y: number }[] = [];
  previewPoint: { x: number; y: number } | null = null;

  // Zoom animation
  private animating = false;
  private animStart = 0;
  private animDuration = 600;
  private animFromView: ViewState | null = null;
  private animTargetCenter: { x: number; y: number } | null = null;
  private animTargetZoom = 1.0;

  private effectIdCounter = 0;
  callbacks: EngineCallbacks = {};

  // ---- lifecycle -----------------------------------------------------------

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D context unavailable');
    this.ctx = ctx;
    this.mapSize = 2048;
    this.worldCoordRange = 1000;
    this.treeCoordRange = 2500;
  }

  async loadImages(): Promise<void> {
    const [bgWorld, bgTree, baseIcon, playerIcon, bossIcon, dungeonIcon, fastTravelIcon, relicGenericIcon] = await Promise.all([
      loadImage(MAP_ASSETS.worldMap),
      loadImage(MAP_ASSETS.treeMap),
      loadImage(MAP_ASSETS.baseIcon),
      loadImage(MAP_ASSETS.playerIcon),
      loadImage(MAP_ASSETS.bossIcon),
      loadImage(MAP_ASSETS.dungeonIcon),
      loadImage(MAP_ASSETS.fastTravelIcon),
      loadImage(MAP_ASSETS.relicGenericIcon),
    ]);
    this.bgWorld = bgWorld;
    this.bgTree = bgTree;
    this.baseIcon = baseIcon;
    this.playerIcon = playerIcon;
    this.bossIcon = bossIcon;
    this.dungeonIcon = dungeonIcon;
    this.fastTravelIcon = fastTravelIcon;
    this.relicGenericIcon = relicGenericIcon;
    this.imagesLoaded = true;
  }

  // ---- coordinate transforms ----------------------------------------------

  /** Image pixel coords → screen pixel coords. */
  imageToScreen(ix: number, iy: number): [number, number] {
    const s = this.view.zoom * this.view.baseScale;
    return [ix * s + this.view.panX, iy * s + this.view.panY];
  }

  /** Screen pixel coords → image pixel coords. */
  screenToImage(sx: number, sy: number): [number, number] {
    const s = this.view.zoom * this.view.baseScale;
    return [(sx - this.view.panX) / s, (sy - this.view.panY) / s];
  }

  /** Image pixel coords → world coords (for the cursor HUD). */
  imageToWorld(ix: number, iy: number): [number, number] {
    const range = this.mapType === 'tree' ? this.treeCoordRange : this.worldCoordRange;
    const wx = (ix / this.mapSize) * (range * 2) - range;
    const wy = range - (iy / this.mapSize) * (range * 2);
    return [wx, wy];
  }

  // ---- view operations -----------------------------------------------------

  resize(width: number, height: number): void {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.fitView();
  }

  fitView(): void {
    const cw = this.canvas.clientWidth;
    const ch = this.canvas.clientHeight;
    if (cw === 0 || ch === 0) return;
    // Use Math.min so the entire map fits in the viewport (contain, not cover).
    const scale = Math.min(cw / this.mapSize, ch / this.mapSize);
    this.view.baseScale = scale;
    this.view.zoom = 1.0;
    this.view.panX = (cw - this.mapSize * scale) / 2;
    this.view.panY = (ch - this.mapSize * scale) / 2;
    this.callbacks.onZoomChange?.(1.0);
  }

  /** Clamp pan so the map image never scrolls off-screen. */
  private clampPan(): void {
    const s = this.view.zoom * this.view.baseScale;
    const cw = this.canvas.clientWidth;
    const ch = this.canvas.clientHeight;
    const imgW = this.mapSize * s;
    const imgH = this.mapSize * s;
    const minPanX = Math.min(0, cw - imgW);
    const maxPanX = Math.max(0, cw - imgW);
    this.view.panX = Math.max(minPanX, Math.min(maxPanX, this.view.panX));
    const minPanY = Math.min(0, ch - imgH);
    const maxPanY = Math.max(0, ch - imgH);
    this.view.panY = Math.max(minPanY, Math.min(maxPanY, this.view.panY));
  }

  zoomAt(screenX: number, screenY: number, factor: number): void {
    const cfg = MAP_CONFIG.zoom;
    const newZoom = Math.max(cfg.min, Math.min(cfg.max, this.view.zoom * factor));
    const actualFactor = newZoom / this.view.zoom;
    if (actualFactor === 1) return;
    // Keep the point under the cursor stationary.
    this.view.panX = screenX - (screenX - this.view.panX) * actualFactor;
    this.view.panY = screenY - (screenY - this.view.panY) * actualFactor;
    this.view.zoom = newZoom;
    this.clampPan();
    this.callbacks.onZoomChange?.(newZoom);
  }

  zoomBy(factor: number): void {
    const cw = this.canvas.clientWidth;
    const ch = this.canvas.clientHeight;
    this.zoomAt(cw / 2, ch / 2, factor);
  }

  panBy(dx: number, dy: number): void {
    this.view.panX += dx;
    this.view.panY += dy;
    this.clampPan();
  }

  resetView(): void {
    this.fitView();
  }

  /** Smoothly animate to center on an image-space point at a given zoom. */
  animateTo(imgX: number, imgY: number, targetZoom: number, durationMs = 600): void {
    const s = this.view.baseScale;
    const targetPanX = this.canvas.clientWidth / 2 - imgX * s * targetZoom;
    const targetPanY = this.canvas.clientHeight / 2 - imgY * s * targetZoom;
    this.animFromView = { ...this.view };
    this.animTargetCenter = { x: targetPanX, y: targetPanY };
    this.animTargetZoom = targetZoom;
    this.animStart = performance.now();
    this.animDuration = durationMs;
    this.animating = true;
  }

  private updateAnimation(now: number): boolean {
    if (!this.animating || !this.animFromView || !this.animTargetCenter) return false;
    const elapsed = now - this.animStart;
    const t = Math.min(1, elapsed / this.animDuration);
    const e = easeOutCubic(t);
    this.view.panX = this.animFromView.panX + (this.animTargetCenter.x - this.animFromView.panX) * e;
    this.view.panY = this.animFromView.panY + (this.animTargetCenter.y - this.animFromView.panY) * e;
    this.view.zoom = this.animFromView.zoom + (this.animTargetZoom - this.animFromView.zoom) * e;
    if (t >= 1) {
      this.animating = false;
      this.animFromView = null;
      this.animTargetCenter = null;
      this.callbacks.onZoomChange?.(this.view.zoom);
    } else {
      this.callbacks.onZoomChange?.(this.view.zoom);
    }
    return true;
  }

  // ---- data management -----------------------------------------------------

  setMapData(bases: MapBase[], players: MapPlayer[], mapSize: number,
             worldRange: number, treeRange: number): void {
    this.mapSize = mapSize;
    this.worldCoordRange = worldRange;
    this.treeCoordRange = treeRange;

    this.baseMarkers = bases
      .map((b) => this.makeBaseMarker(b))
      .filter((m): m is RuntimeBaseMarker => m !== null);
    this.playerMarkers = players
      .map((p) => this.makePlayerMarker(p))
      .filter((m): m is RuntimePlayerMarker => m !== null);
  }

  setPoiData(poiResponse: MapPoiResponse): void {
    const markers: RuntimePoiMarker[] = [];

    // -- Entities: merged boss / alpha / predator list --
    const eSubtypeToKind: Record<string, PoiKind> = { boss: 'boss', alpha: 'boss', predator: 'predator' };
    for (const e of poiResponse.entities) {
      const entKind = eSubtypeToKind[e.subtype] || 'boss';
      const proj = this.mapType === 'tree' ? e.tree_img : e.world_img;
      if (!proj) continue;
      markers.push({
        kind: entKind,
        data: e,
        img_x: proj.x, img_y: proj.y,
        world_x: proj.world_x, world_y: proj.world_y,
        is_hovered: false, is_selected: false,
        current_size: e.subtype === 'predator' ? 40 : 36,
      });
    }

    // -- Dungeons --
    for (const d of poiResponse.dungeons) {
      const proj = this.mapType === 'tree' ? d.tree_img : d.world_img;
      if (!proj) continue;
      markers.push({
        kind: 'dungeon', data: d,
        img_x: proj.x, img_y: proj.y,
        world_x: proj.world_x, world_y: proj.world_y,
        is_hovered: false, is_selected: false, current_size: 36,
      });
    }

    // -- Fast travel --
    for (const ft of poiResponse.fast_travel) {
      const proj = this.mapType === 'tree' ? ft.tree_img : ft.world_img;
      if (!proj) continue;
      markers.push({
        kind: 'fast_travel', data: ft,
        img_x: proj.x, img_y: proj.y,
        world_x: proj.world_x, world_y: proj.world_y,
        is_hovered: false, is_selected: false, current_size: 36,
      });
    }

    // -- Relics --
    for (const r of poiResponse.relics) {
      const proj = this.mapType === 'tree' ? r.tree_img : r.world_img;
      if (!proj) continue;
      markers.push({
        kind: 'relic', data: r,
        img_x: proj.x, img_y: proj.y,
        world_x: proj.world_x, world_y: proj.world_y,
        is_hovered: false, is_selected: false, current_size: 28,
      });
    }

    this.poiMarkers = markers;
  }

  private makeBaseMarker(b: MapBase): RuntimeBaseMarker | null {
    const proj = this.mapType === 'tree' ? b.tree_img : b.world_img;
    if (!proj) return null;
    return {
      kind: 'base',
      data: b,
      img_x: proj.x,
      img_y: proj.y,
      world_x: proj.world_x,
      world_y: proj.world_y,
      glow_alpha: 0,
      glow_increasing: true,
      is_hovered: false,
      is_selected: false,
      shine_pos: 0,
      current_size: MAP_CONFIG.marker.icon.base_size,
    };
  }

  private makePlayerMarker(p: MapPlayer): RuntimePlayerMarker | null {
    const proj = this.mapType === 'tree' ? p.tree_img : p.world_img;
    if (!proj) return null;
    return {
      kind: 'player',
      data: p,
      img_x: proj.x,
      img_y: proj.y,
      world_x: proj.world_x,
      world_y: proj.world_y,
      glow_alpha: 0,
      glow_increasing: true,
      is_hovered: false,
      is_selected: false,
      shine_pos: 0,
      current_size: PLAYER_MARKER.base_size,
    };
  }

  setMapType(type: MapType): void {
    this.mapType = type;
    // Recompute marker positions from the other projection.
    for (const m of this.baseMarkers) {
      const proj = type === 'tree' ? m.data.tree_img : m.data.world_img;
      if (proj) {
        m.img_x = proj.x;
        m.img_y = proj.y;
        m.world_x = proj.world_x;
        m.world_y = proj.world_y;
      }
    }
    for (const m of this.playerMarkers) {
      const proj = type === 'tree' ? m.data.tree_img : m.data.world_img;
      if (proj) {
        m.img_x = proj.x;
        m.img_y = proj.y;
        m.world_x = proj.world_x;
        m.world_y = proj.world_y;
      }
    }
    // Re-project POI markers — filter out those without a valid proj for the new map.
    this.poiMarkers = this.poiMarkers.filter((m) => {
      const proj = type === 'tree'
        ? (m.data as any).tree_img
        : (m.data as any).world_img;
      if (!proj) return false;
      m.img_x = proj.x;
      m.img_y = proj.y;
      m.world_x = proj.world_x;
      m.world_y = proj.world_y;
      return true;
    });
  }

  // ---- hit testing ---------------------------------------------------------

  /** Find the topmost visible marker at screen coords. */
  hitTestMarker(sx: number, sy: number): RuntimeMarker | null {
    // POI markers
    if (this.showRelics) {
      for (const m of [...this.poiMarkers].reverse()) {
        if (m.kind !== 'relic') continue;
        if (!this.isRelicTypeVisible(m)) continue;
        if (this.isInMarkerSimple(m, sx, sy)) return m;
      }
    }
    if (this.showFastTravel) {
      for (const m of [...this.poiMarkers].reverse()) {
        if (m.kind !== 'fast_travel') continue;
        if (this.isInMarkerSimple(m, sx, sy)) return m;
      }
    }
    if (this.showDungeons) {
      for (const m of [...this.poiMarkers].reverse()) {
        if (m.kind !== 'dungeon') continue;
        if (this.isInMarkerSimple(m, sx, sy)) return m;
      }
    }
    if (this.showBosses) {
      for (const m of [...this.poiMarkers].reverse()) {
        if (m.kind !== 'boss') continue;
        if (this.isInMarkerSimple(m, sx, sy)) return m;
      }
    }
    if (this.showPredatorPals) {
      for (const m of [...this.poiMarkers].reverse()) {
        if (m.kind !== 'predator') continue;
        if (this.isInMarkerSimple(m, sx, sy)) return m;
      }
    }
    // Base/player markers
    if (this.showPlayers) {
      for (const m of [...this.playerMarkers].reverse()) {
        if (this.isInMarker(m, sx, sy)) return m;
      }
    }
    if (this.showBases) {
      for (const m of [...this.baseMarkers].reverse()) {
        if (this.isInMarker(m, sx, sy)) return m;
      }
    }
    return null;
  }

  private isInMarker(m: RuntimeMarker, sx: number, sy: number): boolean {
    const [msx, msy] = this.imageToScreen(m.img_x, m.img_y);
    const half = m.current_size / 2 + 4;
    return Math.abs(sx - msx) <= half && Math.abs(sy - msy) <= half;
  }

  /** Simplified AABB hit test for POI markers (no glow offset). */
  private isInMarkerSimple(m: RuntimePoiMarker, sx: number, sy: number): boolean {
    const [msx, msy] = this.imageToScreen(m.img_x, m.img_y);
    const half = m.current_size / 2 + 4;
    return Math.abs(sx - msx) <= half && Math.abs(sy - msy) <= half;
  }

  /** Check if a relic marker's type is visible. */
  private isRelicTypeVisible(m: RuntimePoiMarker): boolean {
    if (m.kind !== 'relic') return false;
    const relicType = (m.data as any).relic_type as string;
    return this.relicTypeVisibility[relicType] !== false;
  }

  /** Find the zone at screen coords. */
  hitTestZone(sx: number, sy: number): Zone | null {
    if (!this.showZones) return null;
    const [ix, iy] = this.screenToImage(sx, sy);
    const [wx, wy] = this.imageToWorld(ix, iy);
    for (const z of [...this.zones].reverse()) {
      if (!z.enabled) continue;
      if (z.type === 'polygon') {
        if (this.pointInPolygon(wx, wy, z.points)) return z;
      } else {
        const zx1 = this.imageToWorld(
          ((z.x1 + this.worldCoordRange) / (this.worldCoordRange * 2)) * this.mapSize, 0)[0];
        // Simpler: check in world coords directly
        if (z.x1 <= wx && wx <= z.x2 && z.y1 <= wy && wy <= z.y2) return z;
      }
    }
    return null;
  }

  private pointInPolygon(px: number, py: number, pts: { x: number; y: number }[]): boolean {
    let inside = false;
    const n = pts.length;
    if (n < 3) return false;
    let j = n - 1;
    for (let i = 0; i < n; i++) {
      const xi = pts[i].x, yi = pts[i].y;
      const xj = pts[j].x, yj = pts[j].y;
      if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }

  // ---- selection -----------------------------------------------------------

  selectMarker(kind: 'base' | 'player' | PoiKind | null, id: string | null): void {
    this.selectedKind = kind;
    this.selectedId = id;
    const isBase = kind === 'base';
    const isPlayer = kind === 'player';
    for (const m of this.baseMarkers) {
      m.is_selected = isBase && m.data.id === id;
      if (m.is_selected) m.glow_alpha = 180;
    }
    for (const m of this.playerMarkers) {
      m.is_selected = isPlayer && m.data.uid === id;
      if (m.is_selected) m.glow_alpha = 180;
    }
    for (const m of this.poiMarkers) {
      m.is_selected = !isBase && !isPlayer && kind === m.kind && (m.data as any).id === id;
    }
  }

  // ---- effects -------------------------------------------------------------

  spawnEffect(kind: 'delete' | 'import' | 'export', imgX: number, imgY: number): void {
    const cfg = MAP_CONFIG.effects[kind];
    this.effects.push({
      id: ++this.effectIdCounter,
      kind,
      x: imgX,
      y: imgY,
      progress: 0,
      start: performance.now(),
      duration: cfg.duration,
    });
  }

  // ---- animation tick ------------------------------------------------------

  tick(now: number): boolean {
    let dirty = false;

    // View animation
    if (this.updateAnimation(now)) dirty = true;

    // Marker glow + shine
    for (const m of [...this.baseMarkers, ...this.playerMarkers]) {
      const isBase = m.kind === 'base';
      const cfg = isBase ? MAP_CONFIG.glow : MAP_CONFIG.glow;
      const speed = isBase ? MAP_CONFIG.glow.animation_speed : PLAYER_MARKER.animation_speed;
      const aMin = isBase ? MAP_CONFIG.glow.selected_alpha_min : PLAYER_MARKER.selected_alpha_min;
      const aMax = isBase ? MAP_CONFIG.glow.selected_alpha_max : PLAYER_MARKER.selected_alpha_max;

      if (m.is_selected) {
        if (m.glow_increasing) {
          m.glow_alpha += speed;
          if (m.glow_alpha >= aMax) m.glow_increasing = false;
        } else {
          m.glow_alpha -= speed;
          if (m.glow_alpha <= aMin) m.glow_increasing = true;
        }
      } else if (m.glow_alpha > 0) {
        m.glow_alpha -= speed * 1.5;
        if (m.glow_alpha < 0) m.glow_alpha = 0;
      }
      m.shine_pos = (m.shine_pos + 2) % 100;

      // Dynamic sizing
      const iconCfg = isBase ? MAP_CONFIG.marker.icon : MAP_CONFIG.marker.icon;
      if (iconCfg.dynamic_sizing) {
        const clamped = Math.max(0.05, Math.min(this.view.zoom, 30.0));
        const rawSize = 48 / Math.sqrt(clamped);
        const newSize = Math.max(iconCfg.size_min, Math.min(iconCfg.size_max, Math.trunc(rawSize)));
        if (newSize !== m.current_size) {
          m.current_size = newSize;
          dirty = true;
        }
      }
    }

    // Effects
    this.effects = this.effects.filter((e) => {
      const elapsed = now - e.start;
      e.progress = Math.min(1, elapsed / e.duration);
      return e.progress < 1;
    });

    // Always dirty if markers have glow/shine animating, or effects active
    if (this.baseMarkers.some((m) => m.is_selected || m.glow_alpha > 0) ||
        this.playerMarkers.some((m) => m.is_selected || m.glow_alpha > 0) ||
        this.effects.length > 0) {
      dirty = true;
    }

    return dirty;
  }

  // ---- rendering -----------------------------------------------------------

  render(): void {
    this.clampPan();
    const ctx = this.ctx;
    const cw = this.canvas.clientWidth;
    const ch = this.canvas.clientHeight;

    // Clear
    ctx.fillStyle = MAP_BG_COLOR;
    ctx.fillRect(0, 0, cw, ch);

    if (!this.imagesLoaded) return;

    // ---- image-space layer (background, zones, rings, effects) ----
    ctx.save();
    const s = this.view.zoom * this.view.baseScale;
    ctx.translate(this.view.panX, this.view.panY);
    ctx.scale(s, s);

    // Background image
    const bg = this.mapType === 'tree' ? this.bgTree : this.bgWorld;
    if (bg) {
      ctx.drawImage(bg, 0, 0, this.mapSize, this.mapSize);
    }

    // Zones (z=3)
    if (this.showZones) {
      this.renderZones(ctx);
    }

    // Radius rings (z=5)
    if (this.showRings && this.mapType === 'world') {
      this.renderRings(ctx);
    }

    // Effects (in image space)
    this.renderEffects(ctx);

    // Zone drawing preview
    if (this.zoneDrawing) {
      this.renderZonePreview(ctx);
    }

    ctx.restore();

    // ---- screen-space layer (markers) ----
    this.renderMarkers(ctx);

    // ---- screen-space layer (zone labels) ----
    if (this.showZones) {
      this.renderZoneLabels(ctx);
    }
  }

  private renderZones(ctx: CanvasRenderingContext2D): void {
    for (const z of this.zones) {
      if (!z.enabled) continue;
      const hovered = z.id === this.hoveredZoneId;
      ctx.fillStyle = 'rgba(255,0,0,0.15)';
      ctx.strokeStyle = hovered ? 'rgba(255,80,80,0.95)' : 'rgba(255,0,0,0.75)';
      ctx.lineWidth = (hovered ? 3 : 2) / (this.view.zoom * this.view.baseScale);

      if (z.type === 'polygon') {
        const pts = z.points.map((p) => this.worldToImage(p.x, p.y));
        if (pts.length < 3) continue;
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        const [x1, y1] = this.worldToImage(z.x1, z.y1);
        const [x2, y2] = this.worldToImage(z.x2, z.y2);
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      }
    }
  }

  private renderZoneLabels(ctx: CanvasRenderingContext2D): void {
    const fontSize = 11;
    ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, sans-serif`;
    ctx.textBaseline = 'top';
    for (const z of this.zones) {
      if (!z.enabled || !z.name) continue;
      let sx: number, sy: number;
      if (z.type === 'polygon') {
        const [ix, iy] = this.worldToImage(z.points[0].x, z.points[0].y);
        [sx, sy] = this.imageToScreen(ix, iy);
      } else {
        const [ix, iy] = this.worldToImage(z.x1, z.y1);
        [sx, sy] = this.imageToScreen(ix, iy);
      }
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      const w = ctx.measureText(z.name).width;
      ctx.fillRect(sx - 2, sy - 2, w + 6, fontSize + 4);
      ctx.fillStyle = 'rgba(255,255,255,0.95)';
      ctx.fillText(z.name, sx + 1, sy);
    }
  }

  /** World coords → image pixel coords (for zones stored in world space). */
  private worldToImage(wx: number, wy: number): [number, number] {
    const range = this.mapType === 'tree' ? this.treeCoordRange : this.worldCoordRange;
    const ix = ((wx + range) / (range * 2)) * this.mapSize;
    const iy = ((range - wy) / (range * 2)) * this.mapSize;
    return [ix, iy];
  }

  private renderRings(ctx: CanvasRenderingContext2D): void {
    if (!this.showBases) return;
    const scale = MAP_SCALE[this.mapType];
    const range = this.mapType === 'tree' ? this.treeCoordRange : this.worldCoordRange;
    for (const m of this.baseMarkers) {
      // Using the corrected area_range to image-px formula:
      // radius_px = (area_range_cm / scale) * (mapSize / (2 * coordRange))
      const radius = area_range_to_image_px(m.data.area_range, scale, this.mapSize, range);
      ctx.beginPath();
      ctx.arc(m.img_x, m.img_y, radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,255,200,0.04)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,255,200,0.55)';
      ctx.lineWidth = 2 / (this.view.zoom * this.view.baseScale);
      ctx.stroke();
    }
  }

  private renderEffects(ctx: CanvasRenderingContext2D): void {
    for (const e of this.effects) {
      const p = easeOutCubic(e.progress);
      if (e.kind === 'delete') {
        const radius = p * 150;
        const alpha = 1 - p;
        ctx.strokeStyle = `rgba(255,80,80,${alpha})`;
        ctx.lineWidth = 5 / (this.view.zoom * this.view.baseScale);
        ctx.beginPath();
        ctx.arc(e.x, e.y, radius, 0, Math.PI * 2);
        ctx.stroke();
        if (radius > 30) {
          ctx.strokeStyle = `rgba(255,150,0,${alpha})`;
          ctx.lineWidth = 3 / (this.view.zoom * this.view.baseScale);
          ctx.beginPath();
          ctx.arc(e.x, e.y, radius - 30, 0, Math.PI * 2);
          ctx.stroke();
        }
        if (p < 0.3) {
          const fa = 0.78 * (1 - p / 0.3);
          ctx.fillStyle = `rgba(255,200,0,${fa})`;
          ctx.beginPath();
          ctx.arc(e.x, e.y, 40, 0, Math.PI * 2);
          ctx.fill();
        }
      } else if (e.kind === 'import') {
        for (let i = 0; i < 3; i++) {
          const phase = (e.progress + i * 0.33) % 1.0;
          const r = phase * 100;
          const a = 0.7 * (1 - phase);
          ctx.strokeStyle = `rgba(0,255,150,${a})`;
          ctx.lineWidth = 3 / (this.view.zoom * this.view.baseScale);
          ctx.beginPath();
          ctx.arc(e.x, e.y, r, 0, Math.PI * 2);
          ctx.stroke();
        }
      } else if (e.kind === 'export') {
        const beamH = p * 200;
        const alpha = 0.78 * (1 - p);
        const grad = ctx.createRadialGradient(e.x, e.y - beamH / 2, 5, e.x, e.y - beamH / 2, 30);
        grad.addColorStop(0, `rgba(100,200,255,${alpha})`);
        grad.addColorStop(1, 'rgba(100,200,255,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(e.x - 20, e.y - beamH, 40, beamH);
      }
    }
  }

  private renderZonePreview(ctx: CanvasRenderingContext2D): void {
    const lineWidth = 2 / (this.view.zoom * this.view.baseScale);
    ctx.setLineDash([10 / (this.view.zoom * this.view.baseScale), 5 / (this.view.zoom * this.view.baseScale)]);
    ctx.strokeStyle = 'rgba(255,0,0,0.8)';
    ctx.fillStyle = 'rgba(255,0,0,0.15)';

    if (this.zoneShape === 'rect' && this.zonePointA && this.previewPoint) {
      const x = Math.min(this.zonePointA.x, this.previewPoint.x);
      const y = Math.min(this.zonePointA.y, this.previewPoint.y);
      const w = Math.abs(this.previewPoint.x - this.zonePointA.x);
      const h = Math.abs(this.previewPoint.y - this.zonePointA.y);
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    } else if (this.zoneShape === 'polygon' && this.polygonPoints.length > 0) {
      ctx.beginPath();
      ctx.moveTo(this.polygonPoints[0].x, this.polygonPoints[0].y);
      for (let i = 1; i < this.polygonPoints.length; i++) {
        ctx.lineTo(this.polygonPoints[i].x, this.polygonPoints[i].y);
      }
      if (this.previewPoint) {
        ctx.lineTo(this.previewPoint.x, this.previewPoint.y);
      }
      ctx.stroke();
      // Vertex dots
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(255,255,0,1)';
      for (const p of this.polygonPoints) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4 / (this.view.zoom * this.view.baseScale), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.setLineDash([]);
  }

  private renderMarkers(ctx: CanvasRenderingContext2D): void {
    if (this.showBases) {
      for (const m of this.baseMarkers) this.drawMarker(ctx, m);
    }
    if (this.showPlayers) {
      for (const m of this.playerMarkers) this.drawMarker(ctx, m);
    }
    // POI markers: render in order
    if (this.showRelics) {
      for (const m of this.poiMarkers) {
        if (m.kind !== 'relic') continue;
        if (!this.isRelicTypeVisible(m)) continue;
        this.drawPoiMarker(ctx, m);
      }
    }
    if (this.showFastTravel) {
      for (const m of this.poiMarkers) {
        if (m.kind !== 'fast_travel') continue;
        this.drawPoiMarker(ctx, m);
      }
    }
    if (this.showDungeons) {
      for (const m of this.poiMarkers) {
        if (m.kind !== 'dungeon') continue;
        this.drawPoiMarker(ctx, m);
      }
    }
    // Bosses + alphas merged under showBosses
    if (this.showBosses) {
      for (const m of this.poiMarkers) {
        if (m.kind !== 'boss') continue;
        this.drawPoiMarker(ctx, m);
      }
    }
    // Predators separate
    if (this.showPredatorPals) {
      for (const m of this.poiMarkers) {
        if (m.kind !== 'predator') continue;
        this.drawPoiMarker(ctx, m);
      }
    }
  }

  private getOrLoadPalPortrait(palId: string): HTMLImageElement | null {
    const key = palId.toLowerCase();
    const cached = this.palPortraitCache.get(key);
    if (cached !== undefined) return cached; // cache hit: img or null (failed/pending)
    const img = new Image();
    img.onload = () => { this.palPortraitCache.set(key, img); };
    img.onerror = () => { this.palPortraitCache.set(key, null); };
    img.src = MAP_ASSETS.palPortrait(palId);
    // Mark as pending so we don't create duplicate requests.
    this.palPortraitCache.set(key, null);
    return null;
  }

  private getOrLoadRelicIcon(relicType: string): HTMLImageElement | null {
    let cached = this.relicIconCache.get(relicType);
    if (cached) return cached;
    const img = new Image();
    img.onload = () => { this.relicIconCache.set(relicType, img); };
    img.src = MAP_ASSETS.relicTypeIcon(relicType);
    this.relicIconCache.set(relicType, img);
    return img;
  }

  private drawPoiMarker(ctx: CanvasRenderingContext2D, m: RuntimePoiMarker): void {
    const [sx, sy] = this.imageToScreen(m.img_x, m.img_y);
    const size = m.current_size;
    const half = size / 2;

    // Selection glow (simple circle, no pulse)
    if (m.is_selected) {
      ctx.beginPath();
      ctx.arc(sx, sy, half + 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.2)';
      ctx.fill();
    }

    // Draw the appropriate icon
    switch (m.kind) {
      case 'boss': {
        const ent = m.data as any;
        const palId = ent.pal || (ent.character_id || '').replace(/^BOSS_/i, '');
        const hasPortrait = palId && palId !== 'None';
        // Pal Icon toggle controls ALL entity portraits (boss, alpha, predator)
        if (this.showPalIcons && hasPortrait) {
          this.drawPalPortrait(ctx, sx, sy, size, palId, false);
        } else {
          const img = this.bossIcon;
          if (img) ctx.drawImage(img, sx - half, sy - half, size, size);
        }
        break;
      }
      case 'predator': {
        const predPalId = (m.data as any).pal as string;
        if (this.showPalIcons && predPalId) {
          this.drawPalPortrait(ctx, sx, sy, size, predPalId, true);
        } else {
          const img = this.bossIcon;
          if (img) ctx.drawImage(img, sx - half, sy - half, size, size);
        }
        break;
      }
      case 'relic': {
        const relicType = (m.data as any).relic_type as string;
        this.drawRelicMarker(ctx, sx, sy, size, relicType);
        break;
      }
    }
  }

  /** Circular-clipped pal portrait, mirroring PSP Rust's ``createPalIconStyle``. */
  private drawPalPortrait(
    ctx: CanvasRenderingContext2D, sx: number, sy: number, size: number,
    palId: string, isPredator: boolean,
  ): void {
    const img = this.getOrLoadPalPortrait(palId);
    const half = size / 2;
    const borderColor = isPredator ? '#ef4444' : '#ffffff';
    const borderWidth = 2;

    ctx.save();

    // Clip to circle (slightly inset for the border)
    ctx.beginPath();
    ctx.arc(sx, sy, half - borderWidth, 0, Math.PI * 2);
    ctx.closePath();
    ctx.clip();

    if (img && img.complete && img.naturalWidth > 0) {
      // Scale+center to cover the circle
      const scale = Math.max(size / img.width, size / img.height);
      const w = img.width * scale;
      const h = img.height * scale;
      ctx.drawImage(img, sx - w / 2, sy - h / 2, w, h);
    } else {
      // Fallback: filled circle with no image
      ctx.fillStyle = isPredator ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.2)';
      ctx.fill();
    }

    ctx.restore();

    // Border circle
    ctx.beginPath();
    ctx.arc(sx, sy, half - borderWidth / 2, 0, Math.PI * 2);
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = borderWidth;
    ctx.stroke();
  }

  /** Relic icon with per-type sprite. */
  private drawRelicMarker(
    ctx: CanvasRenderingContext2D, sx: number, sy: number, size: number, relicType: string,
  ): void {
    const img = this.getOrLoadRelicIcon(relicType);
    const half = size / 2;
    if (img && img.complete && img.naturalWidth > 0) {
      ctx.drawImage(img, sx - half, sy - half, size, size);
    } else {
      // Fallback: use the generic relic icon
      const generic = this.relicGenericIcon;
      if (generic) ctx.drawImage(generic, sx - half, sy - half, size, size);
    }
  }

  private drawMarker(ctx: CanvasRenderingContext2D, m: RuntimeBaseMarker | RuntimePlayerMarker): void {
    const [sx, sy] = this.imageToScreen(m.img_x, m.img_y);
    const size = m.current_size;
    const half = size / 2;
    const icon = m.kind === 'base' ? this.baseIcon : this.playerIcon;
    const glowColor = m.kind === 'base' ? MAP_CONFIG.glow.color : PLAYER_MARKER.glow_color;

    // Glow
    if (MAP_CONFIG.glow.enabled && (m.is_selected || m.glow_alpha > 0 || m.is_hovered)) {
      const alpha = Math.max(
        m.glow_alpha,
        m.is_hovered ? (m.kind === 'base' ? MAP_CONFIG.glow.hover_alpha : PLAYER_MARKER.hover_alpha) : 0,
      );
      const glowR = size * (m.kind === 'base' ? MAP_CONFIG.glow.radius_multiplier : PLAYER_MARKER.radius_multiplier);
      const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowR);
      grad.addColorStop(0, `rgba(${glowColor[0]},${glowColor[1]},${glowColor[2]},${alpha / 255})`);
      grad.addColorStop(0.5, `rgba(${glowColor[0]},${glowColor[1]},${glowColor[2]},${alpha / 2 / 255})`);
      grad.addColorStop(1, `rgba(${glowColor[0]},${glowColor[1]},${glowColor[2]},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
      ctx.fill();
    }

    // Icon
    if (icon) {
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(icon, sx - half, sy - half, size, size);

      // Shine sweep — a diagonal light band sliding left-to-right
      if (m.is_selected || m.is_hovered) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(sx - half, sy - half, size, size);
        ctx.clip();
        const sp = m.shine_pos - 50;
        const bandX = sx - half + (sp / 100) * size;
        const grad = ctx.createLinearGradient(bandX - 10, sy - half, bandX + 15, sy + half);
        grad.addColorStop(0, 'rgba(255,255,255,0)');
        grad.addColorStop(0.5, 'rgba(255,255,255,0.35)');
        grad.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(bandX, sy - half);
        ctx.lineTo(bandX + 15, sy - half);
        ctx.lineTo(bandX - 5, sy + half);
        ctx.lineTo(bandX - 20, sy + half);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
    }
  }
}
