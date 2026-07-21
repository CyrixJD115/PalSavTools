// Editor state as a Svelte 5 runes module.
//
// Ported from the original mappal-palworld Zustand store (src/model/store.ts)
// plus three auxiliary stores (selectionAnchorStore, placeModeStore,
// visibilityStore) and the flyCameraState mutable ref. They are consolidated
// here because (a) Svelte 5 runes (.svelte.ts) give us the same reactive
// primitive Zustand did, and (b) the original split existed mainly to keep
// `src/model/` "off-limits" for UI/interaction state — a file-ownership rule
// that doesn't apply inside this consolidated feature folder.
//
// DESIGN (preserved from the original):
//   - The raw blueprint blob is NEVER mutated while editing. Commands operate
//     on the `objects` array only; reconcileExport() applies the net result
//     onto a structuredClone(raw) at export time. This is the round-trip
//     fidelity guarantee (CLAUDE.md C5, docs/CALIBRATION.md).
//   - Editor state is a command stack (transform / delete / duplicate), not a
//     soup of imperative mutations. Each user action pushes one command;
//     undo/redo walk the stack.
//   - The palbox (typeId "PalBoxV2") is undeletable and unduplicatable — it
//     IS the base camp identity. A blueprint without exactly one breaks imports.
//
// This module is a singleton: module-level `$state` survives SvelteKit route
// changes, so navigating away from /base-editor and back keeps the editor
// session intact (matching the original single-page app behavior).

import { loadBlueprint, serializeBlueprint, type LoadedBlueprint } from "./blueprint";
import { extractCampInfo, extractObjects, type CampInfo } from "./blueprintView";
import { mintGuid, reconcileExport, type DonorLibrary } from "./writeback";
import { validateLinkage } from "./validate";
import type { PlacedObject, Quat, Vec3 } from "./types";

// Donor bundles are 3.4 MB — load them lazily on first palette placement so
// the main bundle (and first paint of every other route) stays lean.
let _donors: DonorLibrary | null = null;
let _donorsPromise: Promise<DonorLibrary> | null = null;
export function getDonors(): Promise<DonorLibrary> {
  if (_donors) return Promise.resolve(_donors);
  if (_donorsPromise) return _donorsPromise;
  _donorsPromise = import("../data/donors.json").then((mod) => {
    const lib = (mod.default as { donors: DonorLibrary }).donors;
    _donors = lib;
    return lib;
  });
  return _donorsPromise;
}

// ---------------------------------------------------------------------------
// Command stack — verbatim data structures from the original store.ts. Plain
// TS, no framework dependency, so this ports byte-for-byte.
// ---------------------------------------------------------------------------

interface TransformState {
  position: Vec3;
  rotation: Quat;
}
export interface TransformEdit {
  id: string;
  position: Vec3;
  rotation: Quat;
}

type Command =
  | { kind: "transform"; entries: { id: string; before: TransformState; after: TransformState }[] }
  | { kind: "delete"; removed: { object: PlacedObject; index: number }[] }
  | { kind: "duplicate"; created: PlacedObject[] };

function applyCommand(objects: PlacedObject[], cmd: Command): PlacedObject[] {
  switch (cmd.kind) {
    case "transform": {
      const byId = new Map(cmd.entries.map((e) => [e.id, e.after]));
      return objects.map((o) => {
        const t = byId.get(o.id);
        return t ? { ...o, position: t.position, rotation: t.rotation } : o;
      });
    }
    case "delete": {
      const ids = new Set(cmd.removed.map((r) => r.object.id));
      return objects.filter((o) => !ids.has(o.id));
    }
    case "duplicate":
      return [...objects, ...cmd.created];
  }
}

function revertCommand(objects: PlacedObject[], cmd: Command): PlacedObject[] {
  switch (cmd.kind) {
    case "transform": {
      const byId = new Map(cmd.entries.map((e) => [e.id, e.before]));
      return objects.map((o) => {
        const t = byId.get(o.id);
        return t ? { ...o, position: t.position, rotation: t.rotation } : o;
      });
    }
    case "delete": {
      // Reinsert at original indices (ascending) to keep ordering stable.
      const result = [...objects];
      for (const r of [...cmd.removed].sort((a, b) => a.index - b.index)) {
        result.splice(Math.min(r.index, result.length), 0, r.object);
      }
      return result;
    }
    case "duplicate": {
      const ids = new Set(cmd.created.map((o) => o.id));
      return objects.filter((o) => !ids.has(o.id));
    }
  }
}

// ---------------------------------------------------------------------------
// Place-hover shape (kept identical to the original placeModeStore.ts — the
// ghost preview writes one of these every pointer move; array-stamp fills
// populate fillPositions).
// ---------------------------------------------------------------------------

export interface PlaceHover {
  position: Vec3;
  rotation: Quat;
  anchorLabel: string;
  anchorId?: string;
  fillPositions?: Vec3[];
  fillCountFull?: number;
}

// ---------------------------------------------------------------------------
// Reactive editor state. Svelte 5 deep-runes: $state on plain objects/arrays
// makes nested mutations reactive, so components reading `editor.objects` or
// `editor.selection` re-render on every command. We use plain assignment
// (replacing the array/object) on every mutation for clarity — same cost as
// in-place mutation under runes.
// ---------------------------------------------------------------------------

class EditorStore {
  fileName = $state<string | null>(null);
  blueprint = $state<LoadedBlueprint | null>(null);
  loadError = $state<string | null>(null);
  objects = $state<PlacedObject[]>([]);
  camp = $state<CampInfo | null>(null);
  selection = $state<string[]>([]);
  undoStack = $state<Command[]>([]);
  redoStack = $state<Command[]>([]);

  // Auxiliary stores (originally separate Zustand stores).
  anchorId = $state<string | null>(null); // selectionAnchorStore
  // placeModeStore fields:
  armedType = $state<string | null>(null);
  hover = $state<PlaceHover | null>(null);
  lastStampPos = $state<Vec3 | null>(null);
  lastStampRotation = $state<Quat | null>(null);
  ghostRotationSteps = $state(0);
  levelOffset = $state(0);
  lockedAnchorId = $state<string | null>(null);
  feedback = $state<string | null>(null);
  // visibilityStore fields:
  hiddenLevels = $state<Set<number>>(new Set());
  soloLevel = $state<number | null>(null);
  // flyCameraState: a plain mutable flag (read synchronously inside a native
  // keydown handler, never rendered). Lives on the store for discoverability.
  isFlying = false;

  private feedbackTimer: ReturnType<typeof setTimeout> | null = null;

  // ---- derived getters ---------------------------------------------------

  /** True when a blueprint is loaded and free of load errors. */
  get isLoaded(): boolean {
    return this.blueprint !== null && this.loadError === null;
  }

  /** Selected PlacedObject[] (in selection order). */
  get selectedObjects(): PlacedObject[] {
    const byId = new Map(this.objects.map((o) => [o.id, o]));
    return this.selection.map((id) => byId.get(id)).filter((o): o is PlacedObject => !!o);
  }

  // ---- load -------------------------------------------------------------

  loadFile(name: string, text: string): void {
    try {
      const bp = loadBlueprint(text);
      const objects = extractObjects(bp.raw);
      const camp = extractCampInfo(bp.raw);
      if (!camp) {
        bp.warnings.push(
          "base_camp transform/area_range not found where expected — radius guardrails disabled for this file",
        );
      }
      this.fileName = name;
      this.blueprint = bp;
      this.loadError = null;
      this.objects = objects;
      this.camp = camp;
      this.selection = [];
      this.undoStack = [];
      this.redoStack = [];
      this.anchorId = null;
      // Reset viewport-only visibility lens on every load (matches the
      // original visibilityStore.reset() call in App.tsx's loadFile).
      this.hiddenLevels = new Set();
      this.soloLevel = null;
      // Disarm placement so a stale armed type from a previous file can't
      // place a ghost into a freshly loaded base.
      this.disarm();
    } catch (err) {
      this.fileName = name;
      this.blueprint = null;
      this.loadError = err instanceof Error ? err.message : String(err);
      this.objects = [];
      this.camp = null;
      this.selection = [];
      this.undoStack = [];
      this.redoStack = [];
      this.anchorId = null;
    }
  }

  clearFile(): void {
    this.fileName = null;
    this.blueprint = null;
    this.loadError = null;
    this.objects = [];
    this.camp = null;
    this.selection = [];
    this.undoStack = [];
    this.redoStack = [];
    this.anchorId = null;
    this.disarm();
  }

  // ---- selection --------------------------------------------------------

  setSelection(ids: string[]): void {
    this.selection = ids;
  }
  toggleSelect(id: string): void {
    this.selection = this.selection.includes(id)
      ? this.selection.filter((x) => x !== id)
      : [...this.selection, id];
  }
  clearSelection(): void {
    this.selection = [];
    this.anchorId = null;
  }
  setAnchor(id: string | null): void {
    this.anchorId = id;
  }

  // ---- commands ---------------------------------------------------------

  private push(cmd: Command): void {
    this.objects = applyCommand(this.objects, cmd);
    this.undoStack = [...this.undoStack, cmd];
    this.redoStack = [];
  }

  /** One undoable step covering all entries (e.g. nudging a multi-selection). */
  transformObjects(edits: TransformEdit[]): void {
    if (edits.length === 0) return;
    const byId = new Map(this.objects.map((o) => [o.id, o]));
    const entries = edits.flatMap((e) => {
      const cur = byId.get(e.id);
      if (!cur) return [];
      return [
        {
          id: e.id,
          before: { position: cur.position, rotation: cur.rotation },
          after: { position: e.position, rotation: e.rotation },
        },
      ];
    });
    if (entries.length > 0) this.push({ kind: "transform", entries });
  }

  deleteSelection(): void {
    const sel = new Set(this.selection);
    // The palbox IS the base (camp anchor, map icon, import identity) — a
    // blueprint without one is broken. It survives any mass-delete sweep.
    const removed = this.objects
      .map((object, index) => ({ object, index }))
      .filter((r) => sel.has(r.object.id) && r.object.typeId !== "PalBoxV2");
    if (removed.length === 0) return;
    this.push({ kind: "delete", removed });
    this.selection = [];
  }

  duplicateSelection(offset: Vec3): void {
    const sel = new Set(this.selection);
    const created = this.objects
      // A duplicated palbox would mean two camp anchors in one file —
      // the exact identity conflict that breaks imports. Skip it.
      .filter((o) => sel.has(o.id) && o.typeId !== "PalBoxV2")
      .map((o): PlacedObject => ({
        ...o,
        id: mintGuid(),
        // A copy of a palette-placed piece is just another placed piece
        // (donor-cloned at export). Only copies of file objects are
        // "duplicate" — chained duplicates keep cloning the real raw entry.
        origin: o.origin === "placed" ? "placed" : "duplicate",
        sourceId:
          o.origin === "original"
            ? o.id
            : o.origin === "duplicate"
              ? o.sourceId
              : undefined,
        position: {
          x: o.position.x + offset.x,
          y: o.position.y + offset.y,
          z: o.position.z + offset.z,
        },
      }));
    if (created.length === 0) return;
    this.push({ kind: "duplicate", created });
    this.selection = created.map((o) => o.id);
  }

  /** Place a new object from the donor library; selects it. */
  placeObject(typeId: string, position: Vec3, rotation: Quat): void {
    if (!this.blueprint) return;
    const created: PlacedObject[] = [
      { id: mintGuid(), typeId, position, rotation, scale: { x: 1, y: 1, z: 1 }, origin: "placed" },
    ];
    // Same command shape as duplicate: apply appends, revert removes.
    this.push({ kind: "duplicate", created });
    this.selection = created.map((o) => o.id);
  }

  undo(): void {
    const cmd = this.undoStack[this.undoStack.length - 1];
    if (!cmd) return;
    this.objects = revertCommand(this.objects, cmd);
    this.undoStack = this.undoStack.slice(0, -1);
    this.redoStack = [...this.redoStack, cmd];
  }

  redo(): void {
    const cmd = this.redoStack[this.redoStack.length - 1];
    if (!cmd) return;
    this.objects = applyCommand(this.objects, cmd);
    this.redoStack = this.redoStack.slice(0, -1);
    this.undoStack = [...this.undoStack, cmd];
  }

  // ---- export -----------------------------------------------------------

  /** Reconcile editor state onto a clone of the raw blob, run the linkage
   *  lint, and serialize. Returns null when nothing is loaded. */
  exportBlueprint(): { filename: string; text: string; notes: string[]; warnings: string[] } | null {
    if (!this.blueprint) return null;
    // Donors must be loaded for "placed" objects; for move/delete/duplicate-
    // only edits the library is never consulted and a still-pending load is
    // harmless. resolveExport({}) returns notes about missing donors with a
    // thrown error only when a placed object's donor genuinely isn't there.
    const donors = _donors ?? {};
    const { raw, notes } = reconcileExport(this.blueprint.raw, this.objects, donors);
    const lintWarnings = validateLinkage(raw);
    if (lintWarnings.length > 0) {
      notes.push(`⚠ export lint found ${lintWarnings.length} linkage issue(s):`, ...lintWarnings);
    } else {
      notes.push("export lint: linkage graph clean");
    }
    const text = serializeBlueprint({ raw, warnings: [] });
    const base = (this.fileName ?? "blueprint.json").replace(/\.json$/i, "");
    return {
      filename: `${base}_edited.json`,
      text,
      notes,
      warnings: [...this.blueprint.warnings, ...lintWarnings],
    };
  }

  // ---- placement arming (placeModeStore actions) ------------------------

  private resetArmedSession(): void {
    this.hover = null;
    this.lastStampPos = null;
    this.lastStampRotation = null;
    this.ghostRotationSteps = 0;
    this.levelOffset = 0;
    this.lockedAnchorId = null;
    this.feedback = null;
  }

  arm(typeId: string): void {
    this.armedType = typeId;
    this.resetArmedSession();
  }
  disarm(): void {
    this.armedType = null;
    this.resetArmedSession();
  }
  toggleArm(typeId: string): void {
    if (this.armedType === typeId) this.disarm();
    else this.arm(typeId);
  }
  setHover(hover: PlaceHover | null): void {
    this.hover = hover;
  }
  setLastStamp(pos: Vec3 | null, rotation: Quat | null): void {
    this.lastStampPos = pos;
    this.lastStampRotation = rotation;
  }
  rotateGhost(): void {
    this.ghostRotationSteps = (this.ghostRotationSteps + 1) % 4;
  }
  adjustLevelOffset(delta: number): void {
    this.levelOffset += delta;
  }
  setAnchorLock(id: string | null): void {
    this.lockedAnchorId = id;
  }
  setFeedback(message: string | null, ttlMs = 1500): void {
    if (this.feedbackTimer !== null) {
      clearTimeout(this.feedbackTimer);
      this.feedbackTimer = null;
    }
    this.feedback = message;
    if (message !== null) {
      this.feedbackTimer = setTimeout(() => {
        this.feedbackTimer = null;
        this.feedback = null;
      }, ttlMs);
    }
  }

  // ---- visibility lens (visibilityStore actions) ------------------------

  toggleLevelHidden(level: number): void {
    const next = new Set(this.hiddenLevels);
    if (next.has(level)) next.delete(level);
    else next.add(level);
    this.hiddenLevels = next;
  }
  toggleSolo(level: number): void {
    this.soloLevel = this.soloLevel === level ? null : level;
  }
  showAll(): void {
    this.hiddenLevels = new Set();
    this.soloLevel = null;
  }
}

/** Module-level singleton editor store. Survives SvelteKit route navigations. */
export const editor = new EditorStore();

/** Placeable palette types — loaded lazily on first palette open. */
export async function loadPlaceableTypes(): Promise<string[]> {
  const donors = await getDonors();
  return Object.keys(donors).filter((t) => t !== "PalBoxV2");
}

// ---------------------------------------------------------------------------
// Visibility helpers (ported verbatim from visibilityStore.ts — pure
// functions over the two visibility fields, used by both the scene and the
// levels panel).
// ---------------------------------------------------------------------------

export function isLevelVisible(level: number, hiddenLevels: Set<number>, soloLevel: number | null): boolean {
  if (soloLevel !== null) return Math.abs(level - soloLevel) <= 1;
  return !hiddenLevels.has(level);
}

export function anyLevelsHidden(hiddenLevels: Set<number>, soloLevel: number | null): boolean {
  return soloLevel !== null || hiddenLevels.size > 0;
}
