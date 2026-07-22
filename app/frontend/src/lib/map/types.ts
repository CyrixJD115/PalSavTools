/**
 * Map runtime types — marker instances, zones, effects. The data-shape types
 * (MapBase, MapPlayer, MapDataResponse, MapType) live in `$types/index` since
 * they mirror the backend schemas.
 */

export type { MapType, MapBase, MapPlayer, MapDataResponse, MapProjection,
  PoiEntity, PoiSubtype, PoiDungeon, PoiFastTravel, PoiRelic,
  MapPoiResponse,
} from '$types/index';

import type { MapBase, MapPlayer,
  PoiEntity, PoiSubtype, PoiDungeon, PoiFastTravel, PoiRelic,
} from '$types/index';

export type MarkerKind = 'base' | 'player';

/** POI marker sub-types (backed by PoiEntity.subtype). */
export type PoiKind = 'boss' | 'alpha' | 'predator' | 'fast_travel' | 'dungeon' | 'relic';

/** Runtime base marker with animation state. */
export interface RuntimeBaseMarker {
  kind: 'base';
  data: MapBase;
  img_x: number;
  img_y: number;
  world_x: number;
  world_y: number;
  glow_alpha: number;
  glow_increasing: boolean;
  is_hovered: boolean;
  is_selected: boolean;
  shine_pos: number;
  current_size: number;
}

/** Runtime player marker with animation state. */
export interface RuntimePlayerMarker {
  kind: 'player';
  data: MapPlayer;
  img_x: number;
  img_y: number;
  world_x: number;
  world_y: number;
  glow_alpha: number;
  glow_increasing: boolean;
  is_hovered: boolean;
  is_selected: boolean;
  shine_pos: number;
  current_size: number;
}

/** Runtime POI marker — no glow/shine, just an icon. */
export interface RuntimePoiMarker {
  kind: PoiKind;
  data: PoiEntity | PoiDungeon | PoiFastTravel | PoiRelic;
  img_x: number;
  img_y: number;
  world_x: number;
  world_y: number;
  is_hovered: boolean;
  is_selected: boolean;
  current_size: number;
}

export type RuntimeMarker = RuntimeBaseMarker | RuntimePlayerMarker | RuntimePoiMarker;

// ---- zones (per-browser, localStorage) ------------------------------------

export interface RectZone {
  id: string;
  name: string;
  enabled: boolean;
  type: 'rect';
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface PolygonZone {
  id: string;
  name: string;
  enabled: boolean;
  type: 'polygon';
  points: { x: number; y: number }[];
}

export type Zone = RectZone | PolygonZone;

export interface ZoneExport {
  zones: Zone[];
  version: number;
}

// ---- effects ---------------------------------------------------------------

export interface MapEffect {
  id: number;
  kind: 'delete' | 'import' | 'export';
  x: number;
  y: number;
  progress: number;
  start: number;
  duration: number;
}

// ---- drawing ---------------------------------------------------------------

export type ZoneShapeType = 'rect' | 'polygon';
