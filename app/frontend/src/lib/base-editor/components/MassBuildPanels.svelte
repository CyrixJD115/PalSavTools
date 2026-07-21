<script lang="ts">
  // The three mass-build tools, presented inline below the toolbar when one
  // is open. Port of FillCirclePanel.tsx + VerticalStackPanel.tsx +
  // RelocateBasePanel.tsx. Logic ported verbatim from the originals; only the
  // markup is restyled with PST V3 tokens.
  import Icon from "@iconify/svelte";
  import Button from "$components/ui/Button.svelte";
  import { t } from "$stores/index";
  import { editor } from "../core/store.svelte";
  import { findPalbox } from "../core/campGeometry";
  import { getTypeEntry } from "../core/objectTypes";
  import { localAxesFromYaw, yawFromQuat } from "../core/coords";
  import {
    addToOverlapIndex,
    buildOverlapIndex,
    findOverlap,
    stampWithOverlapCheck,
  } from "../core/overlapCheck";
  import { GRID_PITCH, VERTICAL_PITCH, type PlacedObject, type Vec3 } from "../core/types";

  let { tool, onclose }: { tool: "circle" | "stack" | "relocate"; onclose: () => void } = $props();

  // ---- Fill Circle ----
  const MAX_RADIUS_TILES = 9;
  const MAX_FILL_COUNT = 400;
  let radiusStr = $state("8");
  let circleResult = $state<string | null>(null);
  let palbox = $derived(findPalbox(editor.objects));
  let armedName = $derived(editor.armedType ? (getTypeEntry(editor.armedType)?.name ?? editor.armedType) : null);
  let isFoundation = $derived(!!editor.armedType && editor.armedType.toLowerCase().includes("foundation"));

  function circleTileCenters(pb: PlacedObject, radiusTiles: number): { x: number; y: number }[] {
    const yaw = yawFromQuat(pb.rotation);
    const { forward, right } = localAxesFromYaw(yaw);
    const maxDist = radiusTiles * GRID_PITCH;
    const tiles: { x: number; y: number }[] = [];
    for (let i = -(radiusTiles + 1); i <= radiusTiles; i++) {
      for (let j = -(radiusTiles + 1); j <= radiusTiles; j++) {
        const localX = (i + 0.5) * GRID_PITCH;
        const localY = (j + 0.5) * GRID_PITCH;
        if (Math.hypot(localX, localY) > maxDist) continue;
        tiles.push({
          x: pb.position.x + localX * forward.x + localY * right.x,
          y: pb.position.y + localX * forward.y + localY * right.y,
        });
      }
    }
    return tiles;
  }
  function handleFill() {
    if (!palbox.palbox || !editor.armedType || !isFoundation) return;
    const parsed = Number(radiusStr);
    const radius = Number.isFinite(parsed) ? Math.min(MAX_RADIUS_TILES, Math.max(1, Math.round(parsed))) : 8;
    const centers = circleTileCenters(palbox.palbox, radius);
    const z = palbox.palbox.position.z;
    const index = buildOverlapIndex(editor.objects);
    let placed = 0;
    let skipped = 0;
    for (const { x, y } of centers) {
      if (placed >= MAX_FILL_COUNT) break;
      const position = { x, y, z };
      if (findOverlap(index, editor.armedType, position, palbox.palbox.rotation)) {
        skipped++;
        continue;
      }
      editor.placeObject(editor.armedType, position, palbox.palbox.rotation);
      addToOverlapIndex(index, { id: "", typeId: editor.armedType, position, rotation: palbox.palbox.rotation, scale: { x: 1, y: 1, z: 1 }, origin: "placed" });
      placed++;
    }
    const cappedNote = placed >= MAX_FILL_COUNT && placed < centers.length ? ` (capped at ${MAX_FILL_COUNT})` : "";
    circleResult = $t("web.base_editor.fill_result", { placed: String(placed), skipped: String(skipped), capped: cappedNote });
  }

  // ---- Vertical Stack ----
  let countStr = $state("4");
  let stackResult = $state<string | null>(null);
  function handleStack(dir: 1 | -1) {
    if (!editor.armedType || !editor.lastStampPos || !editor.lastStampRotation) return;
    const parsed = Number(countStr);
    const count = Number.isFinite(parsed) ? Math.min(64, Math.max(1, Math.round(parsed))) : 4;
    const positions: Vec3[] = [];
    for (let k = 1; k <= count; k++) {
      positions.push({ x: editor.lastStampPos.x, y: editor.lastStampPos.y, z: editor.lastStampPos.z + dir * k * VERTICAL_PITCH });
    }
    const { placed, skipped } = stampWithOverlapCheck(editor.objects, editor.armedType, positions, editor.lastStampRotation, (typeId, pos, rot) => editor.placeObject(typeId, pos, rot));
    editor.setLastStamp(positions[positions.length - 1], editor.lastStampRotation);
    stackResult = $t("web.base_editor.stack_result", { placed: String(placed), name: armedName ?? "", dir: dir > 0 ? $t("web.base_editor.upward") : $t("web.base_editor.downward"), skipped: String(skipped) });
  }
  let stackReady = $derived(!!editor.armedType && !!editor.lastStampPos && !!editor.lastStampRotation);

  // ---- Relocate Base ----
  const round2 = (n: number): number => Math.round(n * 100) / 100;
  let x = $state("0");
  let y = $state("0");
  let z = $state("0");
  // Re-seed when palbox identity changes.
  let lastPalboxId: string | null | undefined = undefined;
  $effect(() => {
    const id = palbox.palbox?.id ?? null;
    if (id !== lastPalboxId) {
      lastPalboxId = id;
      if (palbox.palbox) {
        x = String(round2(palbox.palbox.position.x));
        y = String(round2(palbox.palbox.position.y));
        z = String(round2(palbox.palbox.position.z));
      }
    }
  });
  function handleMove() {
    if (!palbox.palbox) return;
    const target = { x: Number(x), y: Number(y), z: Number(z) };
    if (![target.x, target.y, target.z].every((n) => Number.isFinite(n))) return;
    const delta = {
      x: target.x - palbox.palbox.position.x,
      y: target.y - palbox.palbox.position.y,
      z: target.z - palbox.palbox.position.z,
    };
    editor.transformObjects(
      editor.objects.map((o) => ({
        id: o.id,
        position: { x: o.position.x + delta.x, y: o.position.y + delta.y, z: o.position.z + delta.z },
        rotation: o.rotation,
      })),
    );
  }
</script>

<div class="flex items-start gap-3 text-xs">
  <div class="flex items-center gap-2">
    <Icon icon="lucide:wrench" width={14} class="text-accent-light" />
    <span class="font-semibold text-ink-secondary">
      {#if tool === "circle"}{$t("web.base_editor.fill_circle")}{:else if tool === "stack"}{$t("web.base_editor.vertical_stack")}{:else}{$t("web.base_editor.relocate")}{/if}
    </span>
  </div>

  {#if tool === "circle"}
    {#if !palbox.palbox}
      <span class="text-status-warning">{$t("web.base_editor.fill_unavailable", { reason: palbox.reason ?? "" })}</span>
    {:else}
      <label class="flex items-center gap-1.5 text-ink-secondary">
        {$t("web.base_editor.radius")}
        <input type="number" min="1" max={MAX_RADIUS_TILES} bind:value={radiusStr} class="input w-16 text-xs py-0.5" />
      </label>
      <Button variant="primary" class="h-7 px-2 text-xs" disabled={!isFoundation} onclick={handleFill}>
        {$t("web.base_editor.fill_with", { name: armedName ?? $t("web.base_editor.foundation") })}
      </Button>
      {#if !isFoundation}<span class="text-[10px] text-ink-dim">{$t("web.base_editor.arm_foundation_first")}</span>{/if}
      {#if circleResult}<span class="text-[10px] text-ink-dim">{circleResult}</span>{/if}
    {/if}
  {:else if tool === "stack"}
    <label class="flex items-center gap-1.5 text-ink-secondary">
      {$t("web.base_editor.count")}
      <input type="number" min="1" max="64" bind:value={countStr} class="input w-16 text-xs py-0.5" />
    </label>
    <Button variant="primary" class="h-7 px-2 text-xs" disabled={!stackReady} onclick={() => handleStack(1)}>
      <Icon icon="lucide:arrow-up" width={12} class="inline -mt-0.5" />
      {$t("web.base_editor.stack_up", { name: armedName ?? $t("web.base_editor.armed"), count: String(Number(countStr) || 4) })}
    </Button>
    <Button variant="secondary" class="h-7 px-2 text-xs" disabled={!stackReady} onclick={() => handleStack(-1)}>
      <Icon icon="lucide:arrow-down" width={12} />
    </Button>
    {#if !stackReady}
      <span class="text-[10px] text-ink-dim">
        {editor.armedType ? $t("web.base_editor.stamp_one_first") : $t("web.base_editor.arm_first")}
      </span>
    {/if}
    {#if stackResult}<span class="text-[10px] text-ink-dim">{stackResult}</span>{/if}
  {:else}
    {#if !palbox.palbox}
      <span class="text-status-warning">{$t("web.base_editor.relocate_unavailable", { reason: palbox.reason ?? "" })}</span>
    {:else}
      <span class="text-[10px] text-ink-dim">
        {$t("web.base_editor.current_palbox_pos", { x: String(round2(palbox.palbox.position.x)), y: String(round2(palbox.palbox.position.y)), z: String(round2(palbox.palbox.position.z)) })}
      </span>
      <label class="flex items-center gap-1 text-ink-secondary">X<input type="number" step="any" bind:value={x} class="input w-20 text-xs py-0.5" /></label>
      <label class="flex items-center gap-1 text-ink-secondary">Y<input type="number" step="any" bind:value={y} class="input w-20 text-xs py-0.5" /></label>
      <label class="flex items-center gap-1 text-ink-secondary">Z<input type="number" step="any" bind:value={z} class="input w-20 text-xs py-0.5" /></label>
      <Button variant="primary" class="h-7 px-2 text-xs" onclick={handleMove}>
        {$t("web.base_editor.move_base")}
      </Button>
    {/if}
  {/if}

  <div class="flex-1"></div>
  <button type="button" class="text-ink-dim hover:text-ink-secondary" onclick={onclose} title={$t("web.common.close")}>
    <Icon icon="lucide:x" width={14} />
  </button>
</div>
