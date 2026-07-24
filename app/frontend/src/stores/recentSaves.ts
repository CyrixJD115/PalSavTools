import { writable } from 'svelte/store';

const STORAGE_KEY = 'pst:recent_saves';
const MAX_SAVES = 3;

export interface RecentSave {
  path: string;
  filename: string;
  timestamp: number;
}

function load(): RecentSave[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter(s => typeof s.path === 'string' && typeof s.filename === 'string');
    }
  } catch {
    // Corrupt or disabled storage
  }
  return [];
}

function persist(saves: RecentSave[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saves));
  } catch {
    /* ignore */
  }
}

export const recentSaves = writable<RecentSave[]>(load());

recentSaves.subscribe(persist);

/** Adds a save to the top of the recent list, removing duplicates. */
export function addRecentSave(path: string, filename: string): void {
  recentSaves.update(saves => {
    // Remove if already exists to move it to the top
    const filtered = saves.filter(s => s.path !== path);
    filtered.unshift({ path, filename, timestamp: Date.now() });
    return filtered.slice(0, MAX_SAVES);
  });
}

/** Removes a save from the recent list. */
export function removeRecentSave(path: string): void {
  recentSaves.update(saves => saves.filter(s => s.path !== path));
}
