/**
 * Zone store — per-browser exclusion zones with localStorage persistence.
 * Mirrors the schema of `palworld_aio/managers/zone_manager.py` (kept as
 * exported JSON is interchangeable with the desktop app.
 */

import { writable, get } from 'svelte/store';
import type { Zone, ZoneExport, RectZone, PolygonZone } from '$lib/map/types';

const STORAGE_KEY = 'pst:map:zones';

function load_zones(): Zone[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ZoneExport | Zone[];
    const arr = Array.isArray(parsed) ? parsed : parsed.zones ?? [];
    return arr.filter(is_valid_zone);
  } catch {
    return [];
  }
}

function is_valid_zone(z: unknown): z is Zone {
  if (typeof z !== 'object' || z === null) return false;
  const o = z as Record<string, unknown>;
  if (typeof o.id !== 'string' || typeof o.name !== 'string') return false;
  if (o.type === 'polygon') {
    return Array.isArray(o.points) && o.points.every(is_point);
  }
  return (
    typeof o.x1 === 'number' &&
    typeof o.y1 === 'number' &&
    typeof o.x2 === 'number' &&
    typeof o.y2 === 'number'
  );
}

function is_point(p: unknown): p is { x: number; y: number } {
  if (typeof p !== 'object' || p === null) return false;
  return typeof (p as { x?: unknown }).x === 'number' && typeof (p as { y?: unknown }).y === 'number';
}

function persist(zones: Zone[]): void {
  try {
    const data: ZoneExport = { zones, version: 1 };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* quota or disabled storage — silently ignore */
  }
}

export const zones = writable<Zone[]>(load_zones());

zones.subscribe((zs) => persist(zs));

let _zoneCounter = 0;

export function add_rect_zone(x1: number, y1: number, x2: number, y2: number): string {
  const id = crypto.randomUUID();
  _zoneCounter = get(zones).length + 1;
  const zone: RectZone = {
    id,
    name: `Zone ${_zoneCounter}`,
    enabled: true,
    type: 'rect',
    x1: Math.min(x1, x2),
    x2: Math.max(x1, x2),
    y1: Math.min(y1, y2),
    y2: Math.max(y1, y2),
  };
  zones.update((zs) => [...zs, zone]);
  return id;
}

export function add_polygon_zone(points: { x: number; y: number }[]): string {
  const id = crypto.randomUUID();
  _zoneCounter = get(zones).length + 1;
  const zone: PolygonZone = {
    id,
    name: `Zone ${_zoneCounter}`,
    enabled: true,
    type: 'polygon',
    points,
  };
  zones.update((zs) => [...zs, zone]);
  return id;
}

export function remove_zone(id: string): void {
  zones.update((zs) => zs.filter((z) => z.id !== id));
}

export function rename_zone(id: string, name: string): void {
  zones.update((zs) => zs.map((z) => (z.id === id ? { ...z, name } : z)));
}

export function clear_all_zones(): void {
  zones.set([]);
}

export function export_zones_json(): string {
  return JSON.stringify({ zones: get(zones), version: 1 }, null, 2);
}

export function import_zones_json(text: string): boolean {
  try {
    const parsed = JSON.parse(text) as ZoneExport | Zone[];
    const arr = Array.isArray(parsed) ? parsed : parsed.zones ?? [];
    const valid = arr.filter(is_valid_zone);
    if (valid.length === 0) return false;
    zones.set(valid);
    return true;
  } catch {
    return false;
  }
}

/** Point-in-polygon test (ray casting). Mirrors zone_manager._is_point_in_polygon. */
export function is_point_in_polygon(px: number, py: number, polygon: { x: number; y: number }[]): boolean {
  let inside = false;
  const n = polygon.length;
  if (n < 3) return false;
  let j = n - 1;
  for (let i = 0; i < n; i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
    j = i;
  }
  return inside;
}

export function is_point_in_exclusion(worldX: number, worldY: number): boolean {
  const zs = get(zones);
  for (const z of zs) {
    if (!z.enabled) continue;
    if (z.type === 'polygon') {
      if (is_point_in_polygon(worldX, worldY, z.points)) return true;
    } else {
      if (z.x1 <= worldX && worldX <= z.x2 && z.y1 <= worldY && worldY <= z.y2) return true;
    }
  }
  return false;
}
