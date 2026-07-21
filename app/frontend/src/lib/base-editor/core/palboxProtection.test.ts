// The palbox is the base's identity — mass delete/duplicate must never
// touch it (select-all sweeps are the normal editing gesture for clearing
// large areas, and they always include the palbox).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { editor } from "./store.svelte";

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = readFileSync(path.resolve(here, "../fixtures/calibration_01.json"), "utf8");

describe("palbox protection", () => {
  beforeEach(() => {
    editor.loadFile("calibration_01.json", FIXTURE);
  });

  it("select-all delete removes everything except the palbox", () => {
    editor.setSelection(editor.objects.map((o) => o.id));
    editor.deleteSelection();
    const remaining = editor.objects;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].typeId).toBe("PalBoxV2");
  });

  it("select-all duplicate copies everything except the palbox", () => {
    const before = editor.objects.length;
    editor.setSelection(editor.objects.map((o) => o.id));
    editor.duplicateSelection({ x: 400, y: 0, z: 0 });
    const after = editor.objects;
    expect(after).toHaveLength(before * 2 - 1); // everything doubled but the palbox
    expect(after.filter((o) => o.typeId === "PalBoxV2")).toHaveLength(1);
  });

  it("deleting only the palbox is a no-op", () => {
    const palbox = editor.objects.find((o) => o.typeId === "PalBoxV2")!;
    const countBefore = editor.objects.length;
    editor.setSelection([palbox.id]);
    editor.deleteSelection();
    expect(editor.objects.length).toBe(countBefore);
    expect(editor.undoStack.length).toBe(0); // no empty command pushed
  });
});
