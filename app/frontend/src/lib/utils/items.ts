// Item display-name + icon resolution for inventory grids.
//
// The save's `static_id` (e.g. "AssaultRifle_Default1", "Wood") joins to the
// game-data items.json on the `asset` field. Some save ids carry prefixes
// ("Item_Consumable_Berry", "Weapon_Rifle") that the asset list doesn't, so
// we try a few normalisations before giving up and falling back to a
// pretty-print of the raw id (mirrors the ContainerDetailModal behaviour).

import { browser } from '$app/environment';
import { imgOnError } from '$lib/utils/assetUrl';

export { imgOnError };

export interface ItemMeta {
  name: string;
  icon: string | null;
  rarity: number;
  type_a_display: string;
  type_b_display: string;
  weight: number | null;
  max_stack: number | null;
  durability: number | null;     // DB-listed max durability (weapons/armor)
  magazine_size: number | null;  // DB-listed magazine capacity (weapons)
  description: string | null;
  // Combat stats (weapons/armor):
  physical_atk: number | null;
  magic_atk: number | null;
  physical_def: number | null;
  magic_def: number | null;
  shield_value: number | null;
  hp_value: number | null;
  // Food/consume restore values:
  restore_satiety: number | null;
  restore_sanity: number | null;
  restore_health: number | null;
  // Sneak/crit:
  sneak_atk_rate: number | null;
}

type ItemMap = Map<string, ItemMeta>;

let _cache: ItemMap | null = null;
let _loading: Promise<ItemMap> | null = null;

const FALLBACK_ICON = 'icons/T_icon_unknown.webp';

/** Strip common Palworld id prefixes/suffixes to align with `asset` keys. */
function normaliseId(rawId: string): string[] {
  const id = rawId?.trim();
  if (!id) return [];
  // Always include the raw id first (highest confidence).
  const candidates = [id];
  // Peel known prefixes one at a time, accumulating variants.
  const prefixes = ['Item_', 'Item', 'Weapon_', 'Weapon', 'Armor_', 'Armor', 'Consumable_', 'Consumable'];
  let cur = id;
  for (const p of prefixes) {
    if (cur.startsWith(p) && cur.length > p.length) {
      cur = cur.slice(p.length);
      candidates.push(cur);
    }
  }
  return candidates;
}

/** Pretty-print a raw static_id when no DB entry exists (graceful fallback). */
export function prettyItemId(rawId: string): string {
  if (!rawId) return '';
  return rawId.replace(/^Item_/, '').replace(/_/g, ' ').trim();
}

/** Lazy-load the items DB once and cache it. Returns an empty map on failure. */
export async function loadItemMap(): Promise<ItemMap> {
  if (_cache) return _cache;
  if (_loading) return _loading;
  _loading = (async () => {
    try {
      const res = await fetch('/api/data/game-data/items', { cache: 'force-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      // Endpoint returns {name, data}; data is {items: [...], items_dynamic: [...]}.
      const payload = json?.data ?? json;
      const list: any[] = Array.isArray(payload) ? payload : (payload.items ?? []);
      const map: ItemMap = new Map();
      for (const it of list) {
        const asset = it.asset;
        if (!asset) continue;
        map.set(asset, {
          name: it.name ?? asset,
          icon: it.icon ?? null,
          rarity: it.rarity ?? 0,
          type_a_display: it.type_a_display ?? '',
          type_b_display: it.type_b_display ?? '',
          weight: it.weight ?? null,
          max_stack: it.max_stack ?? null,
          durability: it.durability ?? null,
          magazine_size: it.magazine_size ?? null,
          description: it.description ?? null,
          physical_atk: it.physical_atk ?? null,
          magic_atk: it.magic_atk ?? null,
          physical_def: it.physical_def ?? null,
          magic_def: it.magic_def ?? null,
          shield_value: it.shield_value ?? null,
          hp_value: it.hp_value ?? null,
          restore_satiety: it.restore_satiety ?? null,
          restore_sanity: it.restore_sanity ?? null,
          restore_health: it.restore_health ?? null,
          sneak_atk_rate: it.sneak_atk_rate ?? null,
        });
      }
      _cache = map;
      return map;
    } catch {
      _cache = new Map();
      return _cache;
    } finally {
      _loading = null;
    }
  })();
  return _loading;
}

/** Resolve a single static_id to its display metadata (or a graceful fallback). */
export async function resolveItem(rawId: string): Promise<ItemMeta> {
  const map = await loadItemMap();
  for (const cand of normaliseId(rawId)) {
    const hit = map.get(cand);
    if (hit) return hit;
  }
  return {
    name: prettyItemId(rawId),
    icon: null,
    rarity: 0,
    type_a_display: '',
    type_b_display: '',
    weight: null,
    max_stack: null,
    durability: null,
    magazine_size: null,
    description: null,
    physical_atk: null,
    magic_atk: null,
    physical_def: null,
    magic_def: null,
    shield_value: null,
    hp_value: null,
    restore_satiety: null,
    restore_sanity: null,
    restore_health: null,
    sneak_atk_rate: null,
  };
}

/** Synchronous lookup against the cached map (returns null if not loaded yet). */
export function peekItem(rawId: string): ItemMeta | null {
  if (!_cache) return null;
  for (const cand of normaliseId(rawId)) {
    const hit = _cache.get(cand);
    if (hit) return hit;
  }
  return null;
}

/** Asset URL for an item icon (falls back to the unknown icon). */
export function itemIconUrl(icon: string | null): string {
  return '/api/data/game-data-asset/' + (icon ?? FALLBACK_ICON).replace(/^\//, '');
}

/** Rarity level info: 0=None, 1=Uncommon, 2=Rare, 3=Epic, 4+=Legendary. */
export interface RarityInfo {
  name: string;
  headerClass: string;
  badgeClass: string;
  textClass: string;
}

export function rarityInfo(rarity: number): RarityInfo {
  switch (rarity) {
    case 1:
      return {
        name: 'Uncommon',
        headerClass: 'bg-gradient-to-br from-green-500/30 to-green-800/50 text-green-300 border-green-500/40',
        badgeClass: 'bg-green-500/15 text-green-300 border-green-500/40',
        textClass: 'text-green-400',
      };
    case 2:
      return {
        name: 'Rare',
        headerClass: 'bg-gradient-to-br from-sky-500/30 to-sky-800/50 text-sky-300 border-sky-500/40',
        badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
        textClass: 'text-sky-400',
      };
    case 3:
      return {
        name: 'Epic',
        headerClass: 'bg-gradient-to-br from-purple-500/30 to-purple-800/50 text-purple-300 border-purple-500/40',
        badgeClass: 'bg-purple-500/15 text-purple-300 border-purple-500/40',
        textClass: 'text-purple-400',
      };
    default:
      if (rarity >= 4) {
        return {
          name: 'Legendary',
          headerClass: 'bg-gradient-to-br from-amber-500/30 to-amber-700/50 text-amber-300 border-amber-500/40',
          badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
          textClass: 'text-amber-400',
        };
      }
      return {
        name: 'Common',
        headerClass: 'bg-bg-elevated/60 text-ink-primary border-line/40',
        badgeClass: 'bg-bg-elevated text-ink-secondary border-line/40',
        textClass: 'text-ink-muted',
      };
  }
}

/** True once the item DB has been loaded (so callers can show skeletons). */
export function itemMapLoaded(): boolean {
  return browser && _cache !== null;
}
