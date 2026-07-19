/**
 * User settings store — localStorage-persisted.
 *
 * Models the persistence pattern of `stores/zones.ts` (self-persisting
 * writable under a stable storage key). Holds the user's preferred
 * storage mode and pre-warm behavior for save loads, plus a local copy
 * of the large-save threshold (seeded from /api/health so the client
 * matches the server default unless the user overrides it).
 */

import { writable } from 'svelte/store';
import type { StorageMode } from '$types/index';

const STORAGE_KEY = 'pst:settings';

export interface UserSettings {
  /** Where the decoded save lives after load. */
  storageMode: StorageMode;
  /** Opt-in: sequentially pre-warm every section at load (higher peak RAM). */
  prewarm: boolean;
  /** Files above this size (MB) trigger the storage-mode warning on upload. */
  largeThresholdMb: number;
}

const DEFAULTS: UserSettings = {
  storageMode: 'memory',
  prewarm: false,
  largeThresholdMb: 50,
};

function is_storage_mode(v: unknown): v is StorageMode {
  return v === 'memory' || v === 'disk';
}

function coerce(raw: unknown): UserSettings {
  if (typeof raw !== 'object' || raw === null) return { ...DEFAULTS };
  const o = raw as Record<string, unknown>;
  const out: UserSettings = { ...DEFAULTS };
  if (is_storage_mode(o.storageMode)) out.storageMode = o.storageMode;
  if (typeof o.prewarm === 'boolean') out.prewarm = o.prewarm;
  if (typeof o.largeThresholdMb === 'number' && o.largeThresholdMb > 0) {
    out.largeThresholdMb = o.largeThresholdMb;
  }
  return out;
}

function load(): UserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return coerce(JSON.parse(raw));
  } catch {
    return { ...DEFAULTS };
  }
}

function persist(s: UserSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* quota or disabled storage — silently ignore */
  }
}

export const settings = writable<UserSettings>(load());

settings.subscribe((s) => persist(s));

/** Merge server-side defaults from /api/health into the persisted store. */
export function syncFromHealth(h: {
  storage_mode?: string;
  large_save_threshold_mb?: number;
}): void {
  settings.update((s) => {
    const next = { ...s };
    // Only adopt the server threshold if the user hasn't locally overridden
    // (i.e. the stored value still equals the default sentinel). This keeps
    // an explicit user choice sticky across reloads.
    if (
      typeof h.large_save_threshold_mb === 'number' &&
      h.large_save_threshold_mb > 0 &&
      s.largeThresholdMb === DEFAULTS.largeThresholdMb
    ) {
      next.largeThresholdMb = h.large_save_threshold_mb;
    }
    // We do NOT override storageMode from the server — the user's explicit
    // choice always wins. Server default is only the fallback before the
    // user picks.
    return next;
  });
}

export function setStorageMode(mode: StorageMode): void {
  settings.update((s) => ({ ...s, storageMode: mode }));
}

export function setPrewarm(on: boolean): void {
  settings.update((s) => ({ ...s, prewarm: on }));
}

export function setLargeThresholdMb(mb: number): void {
  if (mb > 0) settings.update((s) => ({ ...s, largeThresholdMb: mb }));
}
