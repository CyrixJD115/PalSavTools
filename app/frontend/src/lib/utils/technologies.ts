// Technology catalog loader for the Tech Tree editor.
//
// The game-data `world.json` carries a 588-entry `technology` array — each
// entry is one unlockable recipe/tech. This module lazy-loads it once, caches
// it, and exposes typed accessors. Mirrors the items.ts loader pattern.

import type { Technology } from '$types/index';

let _cache: Technology[] | null = null;
let _byAsset: Map<string, Technology> | null = null;
let _loading: Promise<Technology[]> | null = null;

/** Lazy-load the technology catalog once and cache it. Returns [] on failure. */
export async function loadTechnologies(): Promise<Technology[]> {
  if (_cache) return _cache;
  if (_loading) return _loading;
  _loading = (async () => {
    try {
      const res = await fetch('/api/data/game-data/world', { cache: 'force-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const payload = json?.data ?? json;
      const list: any[] = Array.isArray(payload) ? payload : (payload.technology ?? []);
      const techs: Technology[] = list.map((t) => ({
        asset: String(t.asset ?? ''),
        name: String(t.name ?? t.asset ?? 'Unknown'),
        icon: t.icon ?? null,
        description: t.description ?? null,
        cost: Number(t.cost ?? 0),
        level_cap: Number(t.level_cap ?? 1),
        type: (t.type === 'boss' ? 'boss' : 'standard') as 'standard' | 'boss',
        is_boss_tech: Boolean(t.is_boss_tech),
        require_technology: String(t.require_technology ?? ''),
        require_tower_boss: String(t.require_tower_boss ?? 'None'),
        unlock_build_objects: Array.isArray(t.unlock_build_objects) ? t.unlock_build_objects : [],
        unlock_item_recipes: Array.isArray(t.unlock_item_recipes) ? t.unlock_item_recipes : [],
      })).filter((t) => t.asset);
      _cache = techs;
      _byAsset = new Map(techs.map((t) => [t.asset, t]));
      return techs;
    } catch {
      _cache = [];
      _byAsset = new Map();
      return _cache;
    } finally {
      _loading = null;
    }
  })();
  return _loading;
}

/** Synchronous lookup against the cached catalog (null if not loaded yet). */
export function peekTechnology(asset: string): Technology | null {
  if (!_byAsset) return null;
  return _byAsset.get(asset) ?? null;
}

/** True once the catalog has been loaded. */
export function technologiesLoaded(): boolean {
  return _cache !== null;
}

/** Asset URL for a technology icon (falls back to the unknown icon). */
export function techIconUrl(icon: string | null): string {
  const FALLBACK = 'icons/T_icon_unknown.webp';
  return '/api/data/game-data-asset/' + (icon ?? FALLBACK).replace(/^\//, '');
}
