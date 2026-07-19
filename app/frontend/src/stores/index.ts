import { writable, derived, get } from 'svelte/store';
import type {
  HealthResponse, LanguagesResponse, LoadProgressPayload, SaveStateResponse, WorldCounts,
} from '$types/index';
import { interpolate } from '$lib/i18n.svelte';
// Inline the default English catalog at build time. This is the critical
// anti-FOUC measure: the i18n store is seeded with real translations BEFORE
// first paint, so $t('web.nav.overview') always returns "Overview" even before
// the persisted-language fetch resolves. Never leave the store empty.
// The 'i18n-default' alias is resolved by both Vite (vite.config.ts) and
// TypeScript (tsconfig.json paths) to <repo>/src/_resources/i18n_web/.
import defaultCatalog from 'i18n-default/en_US.json';

/** Flatten any nested dict into dot-notation keys (the backend does the same). */
function flatten(obj: Record<string, unknown>, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      Object.assign(out, flatten(v as Record<string, unknown>, key));
    } else {
      out[key] = String(v);
    }
  }
  return out;
}

const DEFAULT_KEYS: Record<string, string> = flatten(
  defaultCatalog as Record<string, unknown>,
);

// ---- system ----
export const health = writable<HealthResponse | null>(null);
export const isHealthy = derived(health, ($h) => $h?.status === 'ok');
export const wsConnected = writable(false);
export const languages = writable<LanguagesResponse | null>(null);
export const currentLang = writable('en_US');
// Seeded with the inline English catalog — never empty, so the app renders
// translated from the very first paint. If the persisted language differs,
// +layout.svelte swaps in the correct catalog after mount.
export const i18n = writable<Record<string, string>>(DEFAULT_KEYS);

// ---- save lifecycle ----
export const saveState = writable<SaveStateResponse | null>(null);
export const saveLoaded = derived(saveState, ($s) => !!$s?.loaded);
export const saveSummary = derived(saveState, ($s) => $s?.summary ?? null);
export const saveCounts = derived(saveState, ($s) => $s?.counts ?? null);
export const loadingSave = writable(false);
export const loadError = writable<string | null>(null);

// Live load-stage progress pushed over /ws during save load. Null when no
// load is in progress or when the backend isn't broadcasting stages.
export const loadProgress = writable<LoadProgressPayload | null>(null);

// ---- i18n helper ----
// ``t`` is a derived store whose value is a translator function. The function
// supports {placeholder} interpolation: t('web.players.count', { count: 5 }).
// The second arg is overloaded: a string = literal fallback; an object = params
// for interpolation (falling back to the key itself if missing).
export type Translator = (
  key: string,
  paramsOrFallback?: Record<string, string | number> | string,
) => string;

export const t = derived<[typeof i18n, typeof currentLang], Translator>(
  [i18n, currentLang],
  ([$i18n]: [Record<string, string>, string]): Translator =>
    (key: string, paramsOrFallback?: Record<string, string | number> | string): string => {
      const template = $i18n[key];
      if (template === undefined) {
        // Missing key: use a string fallback if given, else echo the key.
        return typeof paramsOrFallback === 'string' ? paramsOrFallback : key;
      }
      return interpolate(
        template,
        typeof paramsOrFallback === 'object' ? paramsOrFallback : undefined,
      );
    },
);

export function resetSaveData(): void {
  saveState.set(null);
  loadError.set(null);
  loadingSave.set(false);
  loadProgress.set(null);
}

// convenience: read current loaded flag without subscribing
export function isSaveLoaded(): boolean {
  return get(saveLoaded);
}
