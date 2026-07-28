/**
 * Protection store — per-save protection rules + whole-save edit lock.
 *
 * Source of truth is localStorage, keyed by save fingerprint
 * (`pst:protection:<fp>`). On every save load (fingerprint change) the
 * store loads its persisted state and pushes it to the backend so the
 * HTTP gate has the same rules. Local mutations persist immediately and
 * push to the backend in the background.
 *
 * Pattern cloned from `stores/zones.ts` (writable + subscribe→persist) with
 * fingerprint-keyed storage like `settings.ts` but dynamic.
 */

import { writable, get, derived } from 'svelte/store';
import type {
  ProtectionState, ProtectionRule, ProtectionTargetType, ProtectionAction,
} from '$types/index';
import { api } from '$lib/api/client';

const STORAGE_PREFIX = 'pst:protection:';

const EMPTY: ProtectionState = { fingerprint: '', rules: [], edit_locked: false };

function storageKey(fp: string): string {
  return `${STORAGE_PREFIX}${fp}`;
}

function load_persisted(fp: string): ProtectionState {
  if (!fp) return { ...EMPTY };
  try {
    const raw = localStorage.getItem(storageKey(fp));
    if (!raw) return { ...EMPTY, fingerprint: fp };
    const parsed = JSON.parse(raw) as ProtectionState;
    return {
      fingerprint: fp,
      rules: Array.isArray(parsed.rules) ? parsed.rules : [],
      edit_locked: !!parsed.edit_locked,
    };
  } catch {
    return { ...EMPTY, fingerprint: fp };
  }
}

function persist(state: ProtectionState): void {
  if (!state.fingerprint) return;
  try {
    localStorage.setItem(storageKey(state.fingerprint), JSON.stringify(state));
  } catch {
    /* quota or disabled storage — silently ignore */
  }
}

export const protection = writable<ProtectionState>({ ...EMPTY });

// Auto-persist to localStorage on every local change.
protection.subscribe((s) => persist(s));

// Active fingerprint (derived from saveSummary, set via syncToFingerprint).
let _activeFp = '';

/**
 * Derive whether a (target_type, target_id, action) triple is blocked.
 * Note: cascade resolution (guild → bases + members) is done server-side
 * only; this client-side check is a best-effort for UI greying and may
 * under-report cascade blocks. The backend gate is the hard enforcement.
 */
export function isProtected(
  targetType: ProtectionTargetType,
  targetId: string,
  action: ProtectionAction,
): boolean {
  const s = get(protection);
  if (s.edit_locked) return true;
  const tid = targetId.replace(/-/g, '').toLowerCase();
  return s.rules.some(
    (r) =>
      r.target_type === targetType &&
      r.target_id.replace(/-/g, '').toLowerCase() === tid &&
      r.actions.includes(action),
  );
}

/** True if the whole save is edit-locked (master switch). */
export const saveEditLocked = derived(protection, ($p) => $p.edit_locked);

/** All rules for a given target type (for UI panels). */
export function rulesForTargetType(targetType: ProtectionTargetType): ProtectionRule[] {
  return get(protection).rules.filter((r) => r.target_type === targetType);
}

/**
 * Reactive rules-by-target-type store for UI panels. Unlike
 * :func:`rulesForTargetType` (a one-time ``get()`` snapshot), this is a real
 * derived store that recomputes whenever ``protection`` changes — so pages
 * stay in sync after add/remove/toggle without manual refetch.
 */
export function rulesByType(targetType: ProtectionTargetType) {
  return derived(protection, ($p) =>
    $p.rules.filter((r) => r.target_type === targetType),
  );
}

/** Find a direct rule for a specific entity (no cascade). */
export function findRule(
  targetType: ProtectionTargetType,
  targetId: string,
): ProtectionRule | undefined {
  const tid = targetId.replace(/-/g, '').toLowerCase();
  return get(protection).rules.find(
    (r) =>
      r.target_type === targetType &&
      r.target_id.replace(/-/g, '').toLowerCase() === tid,
  );
}

/**
 * Sync the store to a new fingerprint (called when a save loads).
 * Loads persisted rules for this save and pushes them to the backend.
 */
export async function syncToFingerprint(fp: string): Promise<void> {
  if (fp === _activeFp) return;
  _activeFp = fp;
  if (!fp) {
    protection.set({ ...EMPTY });
    return;
  }
  const state = load_persisted(fp);
  protection.set(state);
  // Push to backend so the gate has the right rules for this save.
  try {
    await api.putProtectionState(state);
  } catch {
    /* backend may not be ready yet (load race) — rules are local-first */
  }
}

/**
 * Push the current store state to the backend, debounced.
 *
 * Rapid mutations (add/remove/toggle in quick succession) each used to fire
 * their own async PUT. Network reordering could land an older state last,
 * losing the most recent edit. This coalesces bursts into a single trailing
 * push that always reads the latest store value, so last-write-wins is
 * guaranteed to be the *actual* latest write.
 */
let _pushTimer: ReturnType<typeof setTimeout> | null = null;
let _pushInFlight: Promise<void> | null = null;
const PUSH_DEBOUNCE_MS = 200;

function pushToBackend(): void {
  // Debounce: reset the timer on every call; only the last in a burst fires.
  if (_pushTimer) clearTimeout(_pushTimer);
  _pushTimer = setTimeout(() => {
    _pushTimer = null;
    // Always read the LIVE store state at fire time, not the stale snapshot
    // passed in — this is what guarantees last-write-wins.
    const state = get(protection);
    // Chain after any in-flight push so we don't interleave requests.
    _pushInFlight = (_pushInFlight ?? Promise.resolve()).then(async () => {
      try {
        await api.putProtectionState(state);
      } catch {
        /* stale fingerprint or network — local state is still authoritative */
      }
    }).catch(() => { /* swallow to keep the chain alive */ });
  }, PUSH_DEBOUNCE_MS);
}

// ---- mutators ----------------------------------------------------------

export function addRule(
  targetType: ProtectionTargetType,
  targetId: string,
  actions: ProtectionAction[] = ['delete'],
  cascade = true,
  note = '',
): void {
  const id = crypto.randomUUID();
  const tid = targetId.replace(/-/g, '').toLowerCase();
  const rule: ProtectionRule = {
    id, target_type: targetType, target_id: tid,
    actions: actions.slice(), cascade, source: 'manual', note,
  };
  let changed = false;
  protection.update((s) => {
    // Don't duplicate an identical direct rule.
    const exists = s.rules.some(
      (r) => r.target_type === targetType &&
             r.target_id === tid &&
             r.actions.join(',') === actions.join(','),
    );
    if (exists) return s;
    changed = true;
    return { ...s, rules: [...s.rules, rule] };
  });
  if (changed) pushToBackend();
}

export function removeRule(ruleId: string): void {
  protection.update((s) => ({ ...s, rules: s.rules.filter((r) => r.id !== ruleId) }));
  pushToBackend();
}

export function toggleAction(
  ruleId: string,
  action: ProtectionAction,
): void {
  protection.update((s) => {
    const rules = s.rules.map((r) => {
      if (r.id !== ruleId) return r;
      const actions = r.actions.includes(action)
        ? r.actions.filter((a) => a !== action)
        : [...r.actions, action];
      const fallback: ProtectionAction[] = ['delete'];
      return { ...r, actions: actions.length ? actions : fallback };
    });
    return { ...s, rules };
  });
  pushToBackend();
}

export async function setEditLocked(locked: boolean): Promise<void> {
  protection.update((s) => ({ ...s, edit_locked: locked }));
  // Use the dedicated lock endpoint (lighter than full-state push).
  try {
    await api.putEditLock({ edit_locked: locked });
  } catch {
    // Fallback: the debounced full-state push will sync it.
    pushToBackend();
  }
}

// ---- entity name resolution -------------------------------------------
// Rules store normalized UIDs (lowercase, no hyphens) as target_id, but
// humans need names. This store holds a normalized-uid → display-label map
// per target type, fetched lazily from the list endpoints. Kept here so the
// exclusions page AND ProtectedBadge (in list rows) share one fetch.

export interface EntityLabels {
  player: Record<string, string>;  // normalized uid → "PlayerName"
  guild: Record<string, string>;   // normalized id  → "GuildName"
  base: Record<string, string>;    // normalized id  → "GuildName #2"
  pal: Record<string, string>;     // normalized instance_id → "PalName"
  loaded: boolean;
}

const EMPTY_LABELS: EntityLabels = {
  player: {}, guild: {}, base: {}, pal: {}, loaded: false,
};

export const entityLabels = writable<EntityLabels>({ ...EMPTY_LABELS });

function norm(id: string): string {
  return id.replace(/-/g, '').toLowerCase();
}

/**
 * Fetch all players/guilds/bases and build normalized-id → label maps.
 * Safe to call repeatedly; it replaces the maps wholesale. Called by the
 * exclusions page on mount and after any rule mutation (so newly-added
 * rules resolve immediately).
 */
export async function refreshEntityLabels(): Promise<void> {
  try {
    // Backend caps `limit` at 500 per request (422 above that), so paginate
    // each entity type until we've collected `total` records. Most saves have
    // <500 of each, so this is usually a single round-trip per type.
    const PAGE = 500;
    // Paginate a list endpoint that returns { [key]: T[], total: number }.
    // The response type R is inferred from fetchPage; extract pulls the array.
    async function fetchAll<R, T>(
      fetchPage: (limit: number, offset: number) => Promise<R>,
      extract: (res: R) => T[],
    ): Promise<T[]> {
      const first = await fetchPage(PAGE, 0);
      const total = (first as { total: number }).total;
      const items: T[] = [...extract(first)];
      let offset = items.length;
      while (offset < total && offset < 10000) {
        const page = await fetchPage(PAGE, offset);
        const pageItems = extract(page);
        items.push(...pageItems);
        offset += pageItems.length;
        if (pageItems.length === 0) break;
      }
      return items;
    }

    const [players, guilds, bases, pals] = await Promise.all([
      fetchAll((lim, off) => api.players({ limit: lim, offset: off }), (r) => r.players),
      fetchAll((lim, off) => api.guilds({ limit: lim, offset: off }), (r) => r.guilds),
      fetchAll((lim, off) => api.bases({ limit: lim, offset: off }), (r) => r.bases),
      fetchAll((lim, off) => api.pals({ limit: lim, offset: off }), (r) => r.pals),
    ]);

    const player: Record<string, string> = {};
    for (const p of players) {
      player[norm(p.uid)] = p.name || p.uid;
    }
    const guild: Record<string, string> = {};
    for (const g of guilds) {
      guild[norm(g.id)] = g.name || g.id;
    }
    const base: Record<string, string> = {};
    for (const b of bases) {
      // Bases have no name field; synthesize from guild + position.
      const label = b.guild_name
        ? `${b.guild_name} #${b.base_position ?? '?'}`
        : `Base #${b.base_position ?? '?'}`;
      base[norm(b.id)] = label;
    }
    const pal: Record<string, string> = {};
    for (const p of pals) {
      // Pals: prefer display_name, then nickname, then the species character_id.
      pal[norm(p.instance_id)] = p.display_name || p.nickname || p.character_id || p.instance_id;
    }
    entityLabels.set({ player, guild, base, pal, loaded: true });
  } catch {
    // Non-fatal — the UI falls back to showing the raw ID.
  }
}

/** Look up a display label for a rule target. Falls back to a shortened ID. */
export function labelFor(
  targetType: ProtectionTargetType,
  targetId: string,
): string {
  const labels = get(entityLabels);
  const map = labels[targetType];
  const hit = map?.[norm(targetId)];
  if (hit) return hit;
  // Fallback: shortened raw id.
  return targetId.length > 12 ? `${targetId.slice(0, 8)}…` : targetId;
}
