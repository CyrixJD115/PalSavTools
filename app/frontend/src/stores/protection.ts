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
 * Push the current state to the backend (call after any local mutation).
 * Best-effort: if the push fails, local state + localStorage still hold.
 */
async function pushToBackend(state: ProtectionState): Promise<void> {
  try {
    await api.putProtectionState(state);
  } catch {
    /* stale fingerprint or network — local state is still authoritative */
  }
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
  let pushed: ProtectionState | null = null;
  protection.update((s) => {
    // Don't duplicate an identical direct rule.
    const exists = s.rules.some(
      (r) => r.target_type === targetType &&
             r.target_id === tid &&
             r.actions.join(',') === actions.join(','),
    );
    if (exists) return s;
    const next = { ...s, rules: [...s.rules, rule] };
    pushed = next;
    return next;
  });
  if (pushed) void pushToBackend(pushed);
}

export function removeRule(ruleId: string): void {
  let pushed: ProtectionState | null = null;
  protection.update((s) => {
    const next = { ...s, rules: s.rules.filter((r) => r.id !== ruleId) };
    pushed = next;
    return next;
  });
  if (pushed) void pushToBackend(pushed);
}

export function toggleAction(
  ruleId: string,
  action: ProtectionAction,
): void {
  let pushed: ProtectionState | null = null;
  protection.update((s) => {
    const rules = s.rules.map((r) => {
      if (r.id !== ruleId) return r;
      const actions = r.actions.includes(action)
        ? r.actions.filter((a) => a !== action)
        : [...r.actions, action];
      const fallback: ProtectionAction[] = ['delete'];
      return { ...r, actions: actions.length ? actions : fallback };
    });
    const next = { ...s, rules };
    pushed = next;
    return next;
  });
  if (pushed) void pushToBackend(pushed);
}

export async function setEditLocked(locked: boolean): Promise<void> {
  let pushed: ProtectionState | null = null;
  protection.update((s) => {
    const next = { ...s, edit_locked: locked };
    pushed = next;
    return next;
  });
  if (pushed) {
    // Use the dedicated lock endpoint (lighter than full-state push).
    try {
      await api.putEditLock({ edit_locked: locked });
    } catch {
      void pushToBackend(pushed);
    }
  }
}
