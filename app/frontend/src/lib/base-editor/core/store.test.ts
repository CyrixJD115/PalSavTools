// Tests for the Svelte-runes editor store (store.svelte.ts).
//
// Ported from the original mappal-palworld Zustand store tests. The command
// stack semantics (undo/redo, palbox protection, redo-clear-on-new-command)
// are unchanged — only the store access shape differs (editor.<method>() vs
// useEditorStore.getState().<method>()).
//
// `editor` is a module-level singleton. Every test calls loadFile() first,
// which unconditionally resets objects/selection/undoStack/redoStack, so
// tests don't leak state into each other.

import { describe, test, expect, beforeEach } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { editor } from "./store.svelte";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(here, "../fixtures/calibration_01.json");
const fixtureExists = existsSync(fixturePath);
const fixtureText = fixtureExists ? readFileSync(fixturePath, "utf-8") : "";

const CHEST_ID = "c0faba7d-4197-ff54-3152-51b4a7a83d98";
const HOST_FOUNDATION_ID = "0dc348e9-4e5e-9dd5-8ee9-50bb3297c329";

describe.skipIf(!fixtureExists)("editor store (fixtures/calibration_01.json)", () => {
  beforeEach(() => {
    editor.loadFile("calibration_01.json", fixtureText);
  });

  test("loadFile parses all 22 objects with no load error", () => {
    expect(editor.loadError).toBeNull();
    expect(editor.blueprint).not.toBeNull();
    expect(editor.objects.length).toBe(22);
    expect(editor.undoStack).toEqual([]);
    expect(editor.redoStack).toEqual([]);
  });

  test("transformObjects: undo restores the previous position, redo re-applies it", () => {
    const before = editor.objects.find((o) => o.id === HOST_FOUNDATION_ID)!;
    expect(before).toBeDefined();
    const originalPosition = before.position;

    const newPosition = {
      x: originalPosition.x + 400,
      y: originalPosition.y,
      z: originalPosition.z,
    };
    editor.transformObjects([
      { id: HOST_FOUNDATION_ID, position: newPosition, rotation: before.rotation },
    ]);

    let cur = editor.objects.find((o) => o.id === HOST_FOUNDATION_ID)!;
    expect(cur.position).toEqual(newPosition);
    expect(editor.undoStack.length).toBe(1);
    expect(editor.redoStack.length).toBe(0);

    editor.undo();
    cur = editor.objects.find((o) => o.id === HOST_FOUNDATION_ID)!;
    expect(cur.position).toEqual(originalPosition);
    expect(editor.undoStack.length).toBe(0);
    expect(editor.redoStack.length).toBe(1);

    editor.redo();
    cur = editor.objects.find((o) => o.id === HOST_FOUNDATION_ID)!;
    expect(cur.position).toEqual(newPosition);
    expect(editor.undoStack.length).toBe(1);
    expect(editor.redoStack.length).toBe(0);
  });

  test("deleteSelection: undo restores the object at its original array index", () => {
    const objectsBefore = editor.objects;
    const index = objectsBefore.findIndex((o) => o.id === CHEST_ID);
    expect(index).toBeGreaterThanOrEqual(0);
    const originalCount = objectsBefore.length;

    editor.setSelection([CHEST_ID]);
    editor.deleteSelection();

    expect(editor.objects.length).toBe(originalCount - 1);
    expect(editor.objects.some((o) => o.id === CHEST_ID)).toBe(false);
    // Selection is cleared as part of delete.
    expect(editor.selection).toEqual([]);

    editor.undo();

    const objectsAfterUndo = editor.objects;
    expect(objectsAfterUndo.length).toBe(originalCount);
    expect(objectsAfterUndo[index]?.id).toBe(CHEST_ID);
    expect(objectsAfterUndo).toEqual(objectsBefore);
  });

  test("duplicateSelection: undo removes the copy and leaves the original in place", () => {
    const objectsBefore = editor.objects;
    const originalCount = objectsBefore.length;

    editor.setSelection([CHEST_ID]);
    editor.duplicateSelection({ x: 400, y: 0, z: 0 });

    expect(editor.objects.length).toBe(originalCount + 1);
    const created = editor.objects.find((o) => o.origin === "duplicate");
    expect(created).toBeDefined();
    expect(created!.sourceId).toBe(CHEST_ID);
    // The new copy is selected.
    expect(editor.selection).toEqual([created!.id]);

    editor.undo();

    expect(editor.objects.length).toBe(originalCount);
    expect(editor.objects.some((o) => o.origin === "duplicate")).toBe(false);
    expect(editor.objects).toEqual(objectsBefore);
  });

  test("a new command issued after undo clears the redo stack", () => {
    const before = editor.objects.find((o) => o.id === HOST_FOUNDATION_ID)!;

    editor.transformObjects([
      {
        id: HOST_FOUNDATION_ID,
        position: { ...before.position, x: before.position.x + 400 },
        rotation: before.rotation,
      },
    ]);
    editor.undo();
    expect(editor.redoStack.length).toBe(1);

    // A fresh command (delete) should wipe the redo stack, not just leave it
    // stale — otherwise a later redo() would resurrect an undone edit that
    // no longer applies to the current object set.
    editor.setSelection([CHEST_ID]);
    editor.deleteSelection();

    expect(editor.redoStack).toEqual([]);
    expect(editor.undoStack.length).toBe(1);
  });

  test("exportBlueprint filename is '<original>_edited.json'", () => {
    const result = editor.exportBlueprint();
    expect(result).not.toBeNull();
    expect(result!.filename).toBe("calibration_01_edited.json");
  });

  test("exportBlueprint returns null when nothing is loaded", () => {
    // loadFile with invalid text sets blueprint to null via the catch path.
    editor.loadFile("bad.json", "not json");
    expect(editor.blueprint).toBeNull();
    expect(editor.loadError).not.toBeNull();
    expect(editor.exportBlueprint()).toBeNull();
  });
});

if (!fixtureExists) {
  test.skip("fixture missing — store tests require fixtures/calibration_01.json", () => {});
}
