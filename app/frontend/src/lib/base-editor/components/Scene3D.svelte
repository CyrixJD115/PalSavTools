<script lang="ts">
  // Thin Svelte wrapper around the imperative SceneEngine. Mounts the engine
  // into a host <div>, then wires reactive $effect blocks that re-sync the
  // engine whenever the editor store's relevant fields change. The component
  // owns no three.js objects directly — dispose() on destroy is the engine's
  // job. Matches the PST V3 component style (single root div, full-bleed).
  import { onMount, onDestroy } from "svelte";
  import * as THREE from "three";
  import { editor } from "../core/store.svelte";
  import { ueVecToThree } from "../core/coords";
  import { SceneEngine } from "./scene-engine";

  let host: HTMLDivElement;
  let engine: SceneEngine | null = null;

  // Track the blueprint identity so we only recompute the centroid on a fresh
  // load (NOT on every edit — recentering on every nudge reads as broken).
  let lastBlueprint: unknown = null;

  function recomputeCentroid(): THREE.Vector3 {
    if (editor.objects.length === 0) return new THREE.Vector3();
    const sum = editor.objects.reduce(
      (acc, o) => acc.add(ueVecToThree(o.position)),
      new THREE.Vector3(),
    );
    return sum.multiplyScalar(1 / editor.objects.length);
  }

  onMount(() => {
    engine = new SceneEngine(host, {
      onSceneChanged() {
        // Runes already drive reactivity; this callback exists to make the
        // engine→store bridge explicit. No-op for now.
      },
    });
    // Initial centroid + sync.
    lastBlueprint = editor.blueprint;
    engine.setCentroid(recomputeCentroid());
    engine.syncObjects();
  });

  onDestroy(() => {
    engine?.dispose();
    engine = null;
  });

  // Re-sync object meshes whenever the object list or selection changes.
  $effect(() => {
    // Touch the reactive fields we depend on.
    const _objs = editor.objects;
    const _sel = editor.selection;
    const _bp = editor.blueprint;
    if (!engine) return;
    // Centroid only on fresh load.
    if (_bp !== lastBlueprint) {
      lastBlueprint = _bp;
      engine.setCentroid(recomputeCentroid());
    }
    engine.syncObjects();
  });

  // Visibility lens.
  $effect(() => {
    const _hidden = editor.hiddenLevels;
    const _solo = editor.soloLevel;
    if (!engine) return;
    engine.syncVisibility();
  });

  // Ghost preview follows arming + hover + last-stamp state.
  $effect(() => {
    const _armed = editor.armedType;
    const _hover = editor.hover;
    const _feedback = editor.feedback;
    if (!engine) return;
    // syncGhostMeshes is invoked internally by computeHover; when the user
    // disarms or the hover nulls, we must clear ghosts here.
    if (!_armed || !_hover) {
      // engine.syncGhostMeshes is private — but we can trigger a recompute by
      // asking the engine to re-render via the no-op callback path. For the
      // disarm case, the engine's pointerleave / Escape handlers already call
      // setHover(null); the render loop's updateGhostOverlayLabels hides them.
    }
  });
</script>

<div
  bind:this={host}
  class="relative w-full h-full overflow-hidden bg-bg-base"
  style="touch-action: none;"
></div>

<style>
  /* The host is a positioned ancestor for the engine's absolutely-positioned
     label / hint overlays. */
  :global(.be-viewport-host) {
    position: relative;
  }
</style>
