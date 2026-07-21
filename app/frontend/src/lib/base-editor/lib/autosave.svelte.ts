// Autosave + session restore (ported from src/ui/autosave.ts).
//
// Persists the editor's current export to IndexedDB every 20s (when there are
// pending edits) so a crashed tab / closed browser doesn't lose work. This is
// a convenience net only — PST is still the only way a blueprint reaches the
// game. We write exactly what exportBlueprint() would hand the user for a
// download, just to a local database instead of a file.
//
// Adapted for Svelte runes: instead of subscribing to the Zustand store, we
// expose reactive `autosaveStatus` / `autosaveLastSavedAt` / `restoreRecord`
// via a small .svelte.ts module and mark dirty from the editor store's own
// $effect in the page component.

const DB_NAME = "pst-base-editor";
const STORE_NAME = "autosave";
const RECORD_KEY = "latest";
const SAVE_INTERVAL_MS = 20_000;

export interface AutosaveRecord {
  key: "latest";
  fileName: string;
  text: string;
  savedAt: number;
  editCount: number;
}

export type AutosaveStatus = "idle" | "saved" | "unavailable";

// Reactive UI state (Svelte 5 runes — module-level).
export const autosaveStatus = $state<{ value: AutosaveStatus }>({ value: "idle" });
export const autosaveLastSavedAt = $state<{ value: number | null }>({ value: null });
export const restoreRecord = $state<{ value: AutosaveRecord | null }>({ value: null });
export const restoreBannerDismissed = $state<{ value: boolean }>({ value: false });

export function markAutosaveSaved(savedAt: number): void {
  autosaveStatus.value = "saved";
  autosaveLastSavedAt.value = savedAt;
}
export function markAutosaveUnavailable(): void {
  autosaveStatus.value = "unavailable";
}
export function setRestoreRecord(record: AutosaveRecord | null): void {
  restoreRecord.value = record;
}
export function dismissRestoreBanner(): void {
  restoreBannerDismissed.value = true;
}

/** "12s ago" / "4m ago" / "3h ago" — coarse, header-indicator-friendly. */
export function formatRelativeTime(ms: number): string {
  const deltaSec = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (deltaSec < 5) return "just now";
  if (deltaSec < 60) return `${deltaSec}s ago`;
  const min = Math.round(deltaSec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("indexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("indexedDB open failed"));
  });
}

async function readAutosaveRecordUnsafe(): Promise<AutosaveRecord | null> {
  const db = await openDb();
  return new Promise<AutosaveRecord | null>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).get(RECORD_KEY);
    req.onsuccess = () => resolve((req.result as AutosaveRecord | undefined) ?? null);
    req.onerror = () => reject(req.error ?? new Error("indexedDB read failed"));
  });
}

export async function readAutosaveRecord(): Promise<AutosaveRecord | null> {
  try {
    return await readAutosaveRecordUnsafe();
  } catch {
    return null;
  }
}

async function writeAutosaveRecord(record: AutosaveRecord): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("indexedDB write failed"));
  });
}

export async function deleteAutosaveRecord(): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).delete(RECORD_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("indexedDB delete failed"));
    });
  } catch {
    // best-effort
  }
}

function stripEditedSuffix(filename: string): string {
  return filename.replace(/_edited(?=\.json$)/i, "");
}

// Module-level loop state.
let started = false;
let dirty = false;
let disabled = false;
let intervalId: ReturnType<typeof setInterval> | null = null;

// Set by startAutosave — a thunk that returns the current export snapshot.
let exportThunk: (() => { filename: string; text: string } | null) | null = null;
let isBlueprintLoadedThunk: (() => boolean) | null = null;
let undoCountThunk: (() => number) | null = null;

async function runAutosaveCycle(): Promise<void> {
  if (disabled || !dirty) return;
  if (!isBlueprintLoadedThunk || !isBlueprintLoadedThunk()) return;
  if (!exportThunk) return;
  let result: { filename: string; text: string } | null;
  try {
    result = exportThunk();
  } catch {
    return;
  }
  if (!result) return;
  const record: AutosaveRecord = {
    key: "latest",
    fileName: stripEditedSuffix(result.filename),
    text: result.text,
    savedAt: Date.now(),
    editCount: undoCountThunk ? undoCountThunk() : 0,
  };
  try {
    await writeAutosaveRecord(record);
    dirty = false;
    markAutosaveSaved(record.savedAt);
  } catch {
    disabled = true;
    markAutosaveUnavailable();
  }
}

export interface StartAutosaveOpts {
  exportSnapshot: () => { filename: string; text: string } | null;
  isLoaded: () => boolean;
  undoCount: () => number;
}

/** Wire up the autosave loop. Call once on page mount; returns a teardown. */
export function startAutosave(opts: StartAutosaveOpts): () => void {
  exportThunk = opts.exportSnapshot;
  isBlueprintLoadedThunk = opts.isLoaded;
  undoCountThunk = opts.undoCount;

  if (started) return () => {};
  started = true;
  dirty = false;
  disabled = false;

  // Startup probe: is there a session to restore, and does IndexedDB work?
  readAutosaveRecordUnsafe()
    .then((record) => setRestoreRecord(record))
    .catch(() => {
      disabled = true;
      markAutosaveUnavailable();
    });

  intervalId = setInterval(() => {
    void runAutosaveCycle();
  }, SAVE_INTERVAL_MS);

  const onBeforeUnload = () => {
    void runAutosaveCycle();
  };
  window.addEventListener("beforeunload", onBeforeUnload);

  return () => {
    started = false;
    if (intervalId !== null) clearInterval(intervalId);
    intervalId = null;
    window.removeEventListener("beforeunload", onBeforeUnload);
  };
}

/** Mark the editor dirty (call from a $effect watching editor.undoStack). */
export function markDirty(): void {
  dirty = true;
}
