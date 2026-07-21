// Imperative three.js scene engine for the base editor.
//
// Replaces the original mappal-palworld React-Three-Fiber scene (Scene.tsx,
// ObjectBox.tsx, MarqueeSelect.tsx, FlyCamera.tsx, PlaceMode.tsx,
// RadiusRing.tsx, useKeyboardControls.ts) with a single plain-TS class that
// the Svelte component (Scene3D.svelte) instantiates on mount and disposes
// on destroy. All the verified math (coords.ts, proxyGeometry.ts, snapLattice,
// arrayStamp, overlapCheck, selectionRange, campGeometry, levels) is reused
// unchanged from core/.
//
// The engine holds no Svelte / framework state of its own — it reads/writes
// the reactive `editor` store (store.svelte.ts) directly. The Svelte layer's
// only job is to call `engine.syncObjects()` / `engine.syncSelection()` /
// `engine.syncVisibility()` inside `$effect` blocks when the corresponding
// store fields change.

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { editor, isLevelVisible, type PlaceHover } from "../core/store.svelte";
import {
  GRID_PITCH,
  VERTICAL_PITCH,
  type PlacedObject,
  type Quat,
  type Vec3,
} from "../core/types";
import {
  UNIT_SCALE,
  localAxesFromYaw,
  quatMultiply,
  threeDirToUe,
  threeVecToUe,
  ueQuatToThree,
  ueVecToThree,
  yawFromQuat,
} from "../core/coords";
import { findPalbox } from "../core/campGeometry";
import { levelOf } from "../core/levels";
import { getTypeEntry, resolveType } from "../core/objectTypes";
import { getProxyEdges, getProxyGeometry } from "../core/proxyGeometry";
import { computeStampFill, stampFillNewCount, stampModeFromModifiers } from "../core/arrayStamp";
import { stampWithOverlapCheck } from "../core/overlapCheck";
import {
  classifyLattice,
  edgeYawOffsetDeg,
  rotateQuatByDeg,
  snapCenterLattice,
  snapCornerLattice,
  snapEdgeLattice,
} from "../core/snapLattice";
import { computeRangeSelection } from "../core/selectionRange";
import type { TransformEdit } from "../core/store.svelte";

// ---------------------------------------------------------------------------
// Tuning constants (ported verbatim from the original scene files).
// ---------------------------------------------------------------------------

const MAX_LABELS = 20; // cap concurrent 3D labels (sidebar lists full selection)
const DRAG_THRESHOLD_PX = 6; // < this = click, >= this = drag (orbit/marquee)
const MARQUEE_DRAG_THRESHOLD_PX = 6;

// Fly camera (FlyCamera.tsx)
const LOOK_SENSITIVITY = (0.15 * Math.PI) / 180; // rad/px
const PITCH_LIMIT = (89 * Math.PI) / 180;
const FLY_BASE_SPEED = 6; // m/s
const FLY_SHIFT_MULTIPLIER = 3;
const ORBIT_RESUME_DISTANCE = 8;
const SPEED_HINT_MS = 1200;
const SPEED_MIN = 0.5;
const SPEED_MAX = 200;
const SPEED_SCROLL_FACTOR = 1.15;

// PlaceMode snap tuning
const SNAP_SEARCH_RADIUS = 1200;
const HYSTERESIS_SWITCH_RATIO = 0.6;
const REEVAL_DAMP_DIST = 100;
const LEVEL_PENALTY = 800;
const LEVEL_TOLERANCE = 50;
const OBJECT_RAYCAST_FAR = 3000;
const TARGET_Z_EPSILON = 1e-6;
const LEVEL_RING_RADIUS_M = 1.5 * GRID_PITCH * UNIT_SCALE;

const PALBOX_TYPE_ID = "PalBoxV2";
const WORLD_ANCHOR: Vec3 = { x: 0, y: 0, z: 0 };
const IDENTITY_QUAT: Quat = { x: 0, y: 0, z: 0, w: 1 };

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

// Selection outline color (matches the original cyan).
const OUTLINE_COLOR = 0x5be3ff;

// ---------------------------------------------------------------------------
// SceneEngine
// ---------------------------------------------------------------------------

export interface SceneCallbacks {
  /** Called after every store mutation originating from in-scene interaction
   *  (click-select, marquee, nudge). The Svelte layer uses this to know when
   *  to re-sync dependent UI (sidebar selection fields). Runes reactivity
   *  already covers this, but explicit callbacks make the bridge obvious. */
  onSceneChanged?: () => void;
}

export class SceneEngine {
  private host: HTMLElement;
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private raycaster = new THREE.Raycaster();
  private rafId: number | null = null;

  // Scene-graph registries.
  private objectGroup: THREE.Group;
  private ghostGroup: THREE.Group;
  private ringGroup: THREE.Group;
  /** id -> { mesh, edges, labelDiv } */
  private meshById = new Map<string, { mesh: THREE.Mesh; edges: THREE.LineSegments; label: HTMLDivElement | null }>();
  /** Centroid (three.js space, metres) the whole base is recentred on. */
  private centroid = new THREE.Vector3();
  /** Snapshot of editor.objects at last syncObjects() — used by marquee/raycast. */
  private objectsSnapshot: PlacedObject[] = [];
  private palboxZ: number | null = null;

  // Radius ring (rebuilt on every syncObjects — cheap; one or two meshes).
  private radiusMeshes: THREE.Object3D[] = [];

  // DOM overlays.
  private labelLayer: HTMLDivElement;
  private marqueeBox: HTMLDivElement;
  private flyHint: HTMLDivElement;

  // Pointer bookkeeping for click-vs-drag disambiguation.
  private pointerDownPos: { x: number; y: number } | null = null;

  // Marquee state.
  private marqueeDragging = false;
  private marqueeStartX = 0;
  private marqueeStartY = 0;

  // Fly-camera state.
  private flying = false;
  private flyYaw = 0;
  private flyPitch = 0;
  private flyHeldKeys = new Set<string>();
  private flySpeed = FLY_BASE_SPEED;
  private flyHintTimer: ReturnType<typeof setTimeout> | null = null;

  // Place-mode state (per armed session — reset on arm/disarm/type change).
  private currentAnchorId: string | null = null;
  private lastEvalPoint: { x: number; y: number } | null = null;
  private lastAnchorZ: number | null = null;
  private lastPointerEvent: PointerEvent | null = null;
  private placeRafId: number | null = null;
  private placePendingEvent: PointerEvent | null = null;

  // Bound listener refs (for clean removal in dispose()).
  private boundOnResize: () => void;
  private boundOnPointerDown: (e: PointerEvent) => void;
  private boundOnPointerMove: (e: PointerEvent) => void;
  private boundOnWindowPointerMove: (e: PointerEvent) => void;
  private boundOnWindowPointerUp: (e: PointerEvent) => void;
  private boundOnContextMenu: (e: MouseEvent) => void;
  private boundOnWheel: (e: WheelEvent) => void;
  private boundOnKeyDown: (e: KeyboardEvent) => void;
  private boundOnKeyUp: (e: KeyboardEvent) => void;
  private boundOnBlur: () => void;
  private boundOnPointerLeave: () => void;

  constructor(host: HTMLElement, cb: SceneCallbacks = {}) {
    this.host = host;
    this.callbacks = cb;

    // Renderer.
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(host.clientWidth, host.clientHeight);
    this.renderer.setClearColor(0x0a0e1a, 1); // PST V3 bg.base
    this.renderer.domElement.style.display = "block";
    this.renderer.domElement.style.touchAction = "none";
    host.appendChild(this.renderer.domElement);

    // Scene + camera.
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, host.clientWidth / host.clientHeight, 0.05, 5000);
    this.camera.position.set(14, 16, 14);

    // Lights (matches the original Scene.tsx setup).
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.65));
    const dir = new THREE.DirectionalLight(0xffffff, 0.85);
    dir.position.set(18, 22, -9);
    this.scene.add(dir);

    // Cosmetic infinite ground grid (drei <Grid> equivalent — GridHelper is
    // the plain-three analogue, purely a spatial reference, not a snap grid).
    const grid = new THREE.GridHelper(200, 200, 0x2d3a4e, 0x1e2633);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.5;
    this.scene.add(grid);

    // Orbit controls (drei <OrbitControls> equivalent).
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.1;
    this.controls.target.set(0, 0, 0);

    // Scene-graph groups.
    this.objectGroup = new THREE.Group();
    this.ghostGroup = new THREE.Group();
    this.ringGroup = new THREE.Group();
    this.scene.add(this.ringGroup, this.objectGroup, this.ghostGroup);

    // DOM overlays: label layer (billboarded text via CSS3D-style project),
    // marquee box, fly-speed hint.
    this.labelLayer = document.createElement("div");
    this.labelLayer.style.position = "absolute";
    this.labelLayer.style.inset = "0";
    this.labelLayer.style.pointerEvents = "none";
    this.labelLayer.style.overflow = "hidden";
    host.appendChild(this.labelLayer);

    this.marqueeBox = document.createElement("div");
    this.marqueeBox.style.position = "fixed";
    this.marqueeBox.style.border = "1px solid #5be3ff";
    this.marqueeBox.style.backgroundColor = "rgba(91, 227, 255, 0.12)";
    this.marqueeBox.style.pointerEvents = "none";
    this.marqueeBox.style.zIndex = "10";
    this.marqueeBox.style.display = "none";

    this.flyHint = document.createElement("div");
    this.flyHint.style.position = "absolute";
    this.flyHint.style.right = "12px";
    this.flyHint.style.bottom = "12px";
    this.flyHint.style.padding = "4px 8px";
    this.flyHint.style.borderRadius = "4px";
    this.flyHint.style.background = "rgba(10, 14, 26, 0.85)";
    this.flyHint.style.color = "#5be3ff";
    this.flyHint.style.font = "12px ui-monospace, Consolas, monospace";
    this.flyHint.style.border = "1px solid #2d3a4e";
    this.flyHint.style.display = "none";
    this.flyHint.style.pointerEvents = "none";
    host.appendChild(this.flyHint);

    // Bind all listeners (kept as instance fields so removeEventListener in
    // dispose() hits the exact same references).
    this.boundOnResize = () => this.handleResize();
    this.boundOnPointerDown = (e) => this.onPointerDown(e);
    this.boundOnPointerMove = (e) => this.onPointerMove(e);
    this.boundOnWindowPointerMove = (e) => this.onWindowPointerMove(e);
    this.boundOnWindowPointerUp = (e) => this.onWindowPointerUp(e);
    this.boundOnContextMenu = (e) => e.preventDefault();
    this.boundOnWheel = (e) => this.onWheel(e);
    this.boundOnKeyDown = (e) => this.onKeyDown(e);
    this.boundOnKeyUp = (e) => this.flyHeldKeys.delete(e.key.toLowerCase());
    this.boundOnBlur = () => this.stopFlying();
    this.boundOnPointerLeave = () => {
      if (editor.armedType) editor.setHover(null);
    };

    const dom = this.renderer.domElement;
    dom.addEventListener("pointerdown", this.boundOnPointerDown);
    dom.addEventListener("pointermove", this.boundOnPointerMove);
    dom.addEventListener("pointerleave", this.boundOnPointerLeave);
    dom.addEventListener("contextmenu", this.boundOnContextMenu);
    dom.addEventListener("wheel", this.boundOnWheel, { passive: false });
    window.addEventListener("pointermove", this.boundOnWindowPointerMove);
    window.addEventListener("pointerup", this.boundOnWindowPointerUp);
    window.addEventListener("keydown", this.boundOnKeyDown);
    window.addEventListener("keyup", this.boundOnKeyUp);
    window.addEventListener("blur", this.boundOnBlur);
    window.addEventListener("resize", this.boundOnResize);

    this.startLoop();
  }

  private callbacks: SceneCallbacks;

  // -------------------------------------------------------------------------
  // Public sync API (called from Svelte $effect blocks).
  // -------------------------------------------------------------------------

  /** Rebuild the per-object mesh registry from editor.objects. Also recomputes
   *  the centroid (keyed on blueprint identity, same as the original). */
  syncObjects(): void {
    const objects = editor.objects;
    this.objectsSnapshot = objects;
    this.palboxZ = findPalbox(objects).palbox?.position.z ?? null;

    // Recompute centroid only when a fresh blueprint is loaded (not on every
    // edit), matching the original Scene.tsx behavior.
    if (objects.length === 0) {
      this.centroid.set(0, 0, 0);
    }

    // Diff by id: remove gone, add new, update moved.
    const liveIds = new Set(objects.map((o) => o.id));
    for (const [id, entry] of this.meshById) {
      if (!liveIds.has(id)) {
        this.objectGroup.remove(entry.mesh);
        entry.mesh.geometry.dispose();
        (entry.mesh.material as THREE.Material).dispose();
        this.objectGroup.remove(entry.edges);
        if (entry.label) entry.label.remove();
        this.meshById.delete(id);
      }
    }
    for (const obj of objects) {
      let entry = this.meshById.get(obj.id);
      if (!entry) {
        entry = this.createObjectEntry(obj);
        this.objectGroup.add(entry.mesh);
        this.objectGroup.add(entry.edges);
        this.meshById.set(obj.id, entry);
      }
      this.updateObjectTransform(entry, obj);
      this.updateObjectVisibility(obj);
    }
    this.syncRadiusRing();
    this.syncSelection(); // selection outline state may need refresh
    this.updateLabelPositions();
  }

  /** Update selection outline + opacity on existing meshes (no rebuild). */
  syncSelection(): void {
    const sel = new Set(editor.selection);
    for (const [id, entry] of this.meshById) {
      const selected = sel.has(id);
      const mat = entry.mesh.material as THREE.MeshStandardMaterial;
      if (selected) {
        mat.emissive.setHex(0xffffff);
        mat.emissiveIntensity = 0.45;
      } else {
        mat.emissive.setHex(0x000000);
        mat.emissiveIntensity = 0;
      }
      // Selection outline: toggle a slightly scaled clone-wireframe? Simpler:
      // use the emissive highlight + a brighter edges color when selected.
      const edgeMat = entry.edges.material as THREE.LineBasicMaterial;
      edgeMat.color.setHex(selected ? OUTLINE_COLOR : 0x050505);
      edgeMat.opacity = selected ? 0.9 : 0.35;
    }
    this.updateLabelContents();
    this.updateLabelPositions();
  }

  /** Apply the visibility lens (hiddenLevels / soloLevel) to existing meshes. */
  syncVisibility(): void {
    for (const obj of this.objectsSnapshot) {
      this.updateObjectVisibility(obj);
    }
  }

  // -------------------------------------------------------------------------
  // Per-object mesh construction.
  // -------------------------------------------------------------------------

  private createObjectEntry(obj: PlacedObject): { mesh: THREE.Mesh; edges: THREE.LineSegments; label: HTMLDivElement | null } {
    const resolved = resolveType(obj.typeId);
    const isWorldObject = resolved.category === "world" && !resolved.isUnknownDims;
    const geometry = getProxyGeometry(obj.typeId, resolved.size, resolved.originAtTop, resolved.isUnknownDims);
    const edgesGeometry = getProxyEdges(obj.typeId, resolved.size, resolved.originAtTop, resolved.isUnknownDims);
    const glassOpacity = resolved.materialOpacity;
    const transparent = isWorldObject || glassOpacity !== undefined;
    const opacity = glassOpacity ?? (isWorldObject ? 0.55 : 1);

    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(resolved.color),
      transparent,
      opacity,
      side: THREE.DoubleSide,
      flatShading: true,
      emissive: new THREE.Color(0x000000),
      emissiveIntensity: 0,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.isPlacedObject = true;
    mesh.userData.placedObject = obj;
    mesh.userData.typeId = obj.typeId;

    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x050505,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
    });
    // edgesGeometry is shared/cached; we wrap it (don't dispose in constructor).
    const edges = new THREE.LineSegments(edgesGeometry, edgeMaterial);
    edges.raycast = () => null; // never steal clicks from the parent mesh

    // Label: only the first MAX_LABELS selected ids get one. Created lazily.
    return { mesh, edges, label: null };
  }

  private updateObjectTransform(entry: { mesh: THREE.Mesh; edges: THREE.LineSegments }, obj: PlacedObject): void {
    const pos = ueVecToThree(obj.position).sub(this.centroid);
    const quat = ueQuatToThree(obj.rotation);
    entry.mesh.position.copy(pos);
    entry.mesh.quaternion.copy(quat);
    entry.edges.position.copy(pos);
    entry.edges.quaternion.copy(quat);
    // Keep the userData.placedObject reference fresh so raycast hit-tests
    // resolve to the live object even after an edit kept the same mesh.
    entry.mesh.userData.placedObject = obj;
    entry.mesh.userData.typeId = obj.typeId;
  }

  private updateObjectVisibility(obj: PlacedObject): void {
    const entry = this.meshById.get(obj.id);
    if (!entry) return;
    const level = levelOf(obj.position.z, this.palboxZ);
    const visible = isLevelVisible(level, editor.hiddenLevels, editor.soloLevel);
    entry.mesh.visible = visible;
    entry.edges.visible = visible;
    if (entry.label) entry.label.style.display = visible ? "block" : "none";
  }

  // -------------------------------------------------------------------------
  // Radius ring (rebuilt every syncObjects — at most a disc + ring mesh).
  // -------------------------------------------------------------------------

  private syncRadiusRing(): void {
    for (const m of this.radiusMeshes) {
      this.ringGroup.remove(m);
      (m as THREE.Mesh).geometry?.dispose();
      ((m as THREE.Mesh).material as THREE.Material)?.dispose();
    }
    this.radiusMeshes = [];
    const camp = editor.camp;
    const { palbox } = findPalbox(this.objectsSnapshot);
    if (!camp || !palbox) return;

    const center = ueVecToThree(palbox.position).sub(this.centroid);
    const radius = camp.areaRange * UNIT_SCALE;
    const group = new THREE.Group();
    group.position.set(center.x, center.y - 0.02, center.z);
    group.rotation.set(-Math.PI / 2, 0, 0);

    const discMat = new THREE.MeshBasicMaterial({
      color: 0x5be3ff,
      transparent: true,
      opacity: 0.06,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const disc = new THREE.Mesh(new THREE.CircleGeometry(radius, 64), discMat);
    disc.raycast = () => null;
    group.add(disc);

    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x5be3ff,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(new THREE.RingGeometry(radius * 0.985, radius, 64), ringMat);
    ring.raycast = () => null;
    group.add(ring);

    this.ringGroup.add(group);
    this.radiusMeshes.push(group);
  }

  // -------------------------------------------------------------------------
  // Labels — PST-styled floating text projected to screen space each frame.
  // -------------------------------------------------------------------------

  private updateLabelContents(): void {
    const sel = editor.selection;
    const labelIds = new Set(sel.slice(0, MAX_LABELS));
    for (const [id, entry] of this.meshById) {
      const want = labelIds.has(id);
      const have = entry.label !== null;
      if (want && !have) {
        const obj = this.objectsSnapshot.find((o) => o.id === id);
        if (!obj) continue;
        const name = getTypeEntry(obj.typeId)?.name ?? obj.typeId;
        const div = document.createElement("div");
        div.textContent = name;
        div.style.position = "absolute";
        div.style.pointerEvents = "none";
        div.style.padding = "1px 6px";
        div.style.borderRadius = "3px";
        div.style.background = "rgba(10, 14, 26, 0.85)";
        div.style.color = "#e3f2fd";
        div.style.font = "11px ui-monospace, Consolas, monospace";
        div.style.border = "1px solid #2d3a4e";
        div.style.whiteSpace = "nowrap";
        div.style.transform = "translate(-50%, -100%)";
        this.labelLayer.appendChild(div);
        entry.label = div;
      } else if (!want && have) {
        entry.label!.remove();
        entry.label = null;
      }
    }
  }

  private updateLabelPositions(): void {
    const rect = this.host.getBoundingClientRect();
    const v = new THREE.Vector3();
    for (const [id, entry] of this.meshById) {
      if (!entry.label) continue;
      const obj = this.objectsSnapshot.find((o) => o.id === id);
      if (!obj) continue;
      // Compute label anchor: top of the shape in local Y, then to world.
      const geo = entry.mesh.geometry;
      if (!geo.boundingBox) geo.computeBoundingBox();
      const topY = geo.boundingBox?.max.y ?? 0;
      v.set(0, topY + 0.2, 0).applyQuaternion(entry.mesh.quaternion).add(entry.mesh.position);
      v.project(this.camera);
      if (v.z < -1 || v.z > 1) {
        entry.label.style.display = "none";
        continue;
      }
      const px = (v.x * 0.5 + 0.5) * rect.width;
      const py = (-v.y * 0.5 + 0.5) * rect.height;
      entry.label.style.display = "block";
      entry.label.style.left = `${px}px`;
      entry.label.style.top = `${py}px`;
    }
  }

  // -------------------------------------------------------------------------
  // Render loop.
  // -------------------------------------------------------------------------

  private startLoop(): void {
    const loop = () => {
      this.rafId = requestAnimationFrame(loop);
      if (this.flying) this.updateFlyMovement();
      else this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this.updateLabelPositions();
      this.updateGhostOverlayLabels();
    };
    this.rafId = requestAnimationFrame(loop);
  }

  private handleResize(): void {
    const w = this.host.clientWidth;
    const h = this.host.clientHeight;
    if (w === 0 || h === 0) return;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // -------------------------------------------------------------------------
  // Pointer — click select / marquee / place / orbit drag disambiguation.
  // -------------------------------------------------------------------------

  private onPointerDown(e: PointerEvent): void {
    this.pointerDownPos = { x: e.clientX, y: e.clientY };

    // RMB = fly camera (handled in startFlying).
    if (e.button === 2) {
      e.preventDefault();
      this.startFlying();
      return;
    }
    if (e.button !== 0) return;

    // Shift+LMB drag = marquee (disabled while armed).
    if (e.shiftKey && !editor.armedType) {
      this.marqueeDragging = true;
      this.marqueeStartX = e.clientX;
      this.marqueeStartY = e.clientY;
      this.controls.enabled = false;
      document.body.appendChild(this.marqueeBox);
      this.positionMarquee(this.marqueeStartX, this.marqueeStartY, this.marqueeStartX, this.marqueeStartY);
    }
  }

  private onPointerMove(e: PointerEvent): void {
    // Place-mode hover tracking (rAF-coalesced).
    if (editor.armedType) {
      this.lastPointerEvent = e;
      this.placePendingEvent = e;
      if (this.placeRafId === null) {
        this.placeRafId = requestAnimationFrame(() => {
          this.placeRafId = null;
          if (this.placePendingEvent) this.computeHover(this.placePendingEvent, false);
        });
      }
    }
  }

  private onWindowPointerMove(e: PointerEvent): void {
    // Fly look.
    if (this.flying) {
      this.flyYaw -= e.movementX * LOOK_SENSITIVITY;
      this.flyPitch -= e.movementY * LOOK_SENSITIVITY;
      this.flyPitch = Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, this.flyPitch));
      return;
    }
    // Marquee drag.
    if (this.marqueeDragging) {
      this.positionMarquee(this.marqueeStartX, this.marqueeStartY, e.clientX, e.clientY);
    }
  }

  private onWindowPointerUp(e: PointerEvent): void {
    if (e.button === 2 && this.flying) {
      this.stopFlying();
      return;
    }
    if (!this.marqueeDragging) {
      // Click (no drag) — handle select / place / clear.
      if (e.button !== 0) return;
      const down = this.pointerDownPos;
      this.pointerDownPos = null;
      const moved = down ? Math.hypot(e.clientX - down.x, e.clientY - down.y) : 0;
      if (moved > DRAG_THRESHOLD_PX) return; // was an orbit drag
      this.handleClick(e);
      return;
    }

    // Marquee release.
    this.marqueeDragging = false;
    this.marqueeBox.style.display = "none";
    this.marqueeBox.remove();
    this.controls.enabled = true;

    const dist = Math.hypot(e.clientX - this.marqueeStartX, e.clientY - this.marqueeStartY);
    if (dist <= MARQUEE_DRAG_THRESHOLD_PX) return;

    const rect = this.renderer.domElement.getBoundingClientRect();
    const x0 = Math.min(this.marqueeStartX, e.clientX) - rect.left;
    const x1 = Math.max(this.marqueeStartX, e.clientX) - rect.left;
    const y0 = Math.min(this.marqueeStartY, e.clientY) - rect.top;
    const y1 = Math.max(this.marqueeStartY, e.clientY) - rect.top;

    const hits: string[] = [];
    const v = new THREE.Vector3();
    for (const o of this.objectsSnapshot) {
      const level = levelOf(o.position.z, this.palboxZ);
      if (!isLevelVisible(level, editor.hiddenLevels, editor.soloLevel)) continue;
      v.copy(ueVecToThree(o.position)).sub(this.centroid);
      v.project(this.camera);
      if (v.z < -1 || v.z > 1) continue;
      const px = (v.x * 0.5 + 0.5) * rect.width;
      const py = (-v.y * 0.5 + 0.5) * rect.height;
      if (px >= x0 && px <= x1 && py >= y0 && py <= y1) hits.push(o.id);
    }
    if (hits.length === 0) return;
    editor.setSelection([...new Set([...editor.selection, ...hits])]);
    this.callbacks.onSceneChanged?.();
  }

  private positionMarquee(x0: number, y0: number, x1: number, y1: number): void {
    this.marqueeBox.style.left = `${Math.min(x0, x1)}px`;
    this.marqueeBox.style.top = `${Math.min(y0, y1)}px`;
    this.marqueeBox.style.width = `${Math.abs(x1 - x0)}px`;
    this.marqueeBox.style.height = `${Math.abs(y1 - y0)}px`;
    this.marqueeBox.style.display = "block";
  }

  private handleClick(e: PointerEvent): void {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    this.raycaster.far = OBJECT_RAYCAST_FAR;

    // Place mode: clicking places at the ghost's current position (regardless
    // of whether an existing object was hit underneath).
    if (editor.armedType) {
      const hover = editor.hover;
      if (hover) {
        const mode = stampModeFromModifiers(e.shiftKey, e.ctrlKey);
        const positions =
          mode === "single"
            ? [hover.position]
            : computeStampFill(editor.lastStampPos, hover.position, yawFromQuat(hover.rotation), mode);
        const { placed, skipped } = stampWithOverlapCheck(
          this.objectsSnapshot,
          editor.armedType,
          positions,
          hover.rotation,
          (typeId, pos, rot) => editor.placeObject(typeId, pos, rot),
        );
        if (mode === "single") {
          if (placed === 0) editor.setFeedback("already placed here");
        } else {
          editor.setFeedback(`placed ${placed}, skipped ${skipped} overlapping`);
        }
        editor.setLastStamp(hover.position, hover.rotation);
        if (placed > 0) editor.setHover(null);
      }
      return;
    }

    // Selection: raycast placed-object meshes only.
    const meshes = [...this.meshById.values()]
      .filter((e) => e.mesh.visible)
      .map((e) => e.mesh);
    const hits = this.raycaster.intersectObjects(meshes, false);
    const hitObj = hits[0]?.object.userData.placedObject as PlacedObject | undefined;

    if (!hitObj) {
      // Empty-space click clears selection.
      editor.clearSelection();
      this.callbacks.onSceneChanged?.();
      return;
    }

    this.handleSelect(hitObj.id, { shiftKey: e.shiftKey, ctrlKey: e.ctrlKey || e.metaKey, altKey: e.altKey });
    this.callbacks.onSceneChanged?.();
  }

  /** Click-selection semantics — straight port of Scene.tsx's handleSelect. */
  private handleSelect(id: string, mods: { shiftKey: boolean; ctrlKey: boolean; altKey: boolean }): void {
    const objects = this.objectsSnapshot;
    const clicked = objects.find((o) => o.id === id);
    if (!clicked) return;

    if (mods.altKey) {
      const sameType = objects.filter((o) => o.typeId === clicked.typeId).map((o) => o.id);
      editor.setSelection(mods.shiftKey ? [...new Set([...editor.selection, ...sameType])] : sameType);
      editor.setAnchor(id);
      return;
    }
    if (mods.shiftKey) {
      const anchorObj = objects.find((o) => o.id === editor.anchorId);
      if (!anchorObj) {
        editor.setSelection([id]);
      } else {
        const rangeIds = computeRangeSelection(anchorObj, clicked, objects);
        editor.setSelection([...new Set([...editor.selection, ...rangeIds])]);
      }
      editor.setAnchor(id);
      return;
    }
    if (mods.ctrlKey) {
      editor.toggleSelect(id);
      editor.setAnchor(id);
      return;
    }
    editor.setSelection([id]);
    editor.setAnchor(id);
  }

  // -------------------------------------------------------------------------
  // Fly camera (FlyCamera.tsx port).
  // -------------------------------------------------------------------------

  private startFlying(): void {
    if (this.flying) return;
    this.flying = true;
    editor.isFlying = true;
    this.flyHeldKeys.clear();
    const euler = new THREE.Euler().setFromQuaternion(this.camera.quaternion, "YXZ");
    this.flyYaw = euler.y;
    this.flyPitch = euler.x;
    this.controls.enabled = false;
  }

  private stopFlying(): void {
    if (!this.flying) return;
    this.flying = false;
    editor.isFlying = false;
    this.flyHeldKeys.clear();
    // Park orbit target a few metres ahead so orbit resumes from this view.
    const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
    this.controls.target.copy(this.camera.position).addScaledVector(forward, ORBIT_RESUME_DISTANCE);
    this.controls.enabled = true;
    this.controls.update();
    if (this.flyHintTimer !== null) {
      clearTimeout(this.flyHintTimer);
      this.flyHintTimer = null;
    }
    this.flyHint.style.display = "none";
  }

  private updateFlyMovement(): void {
    this.camera.quaternion.setFromEuler(new THREE.Euler(this.flyPitch, this.flyYaw, 0, "YXZ"));
    const delta = this.clockDelta();
    const speed = this.flySpeed * (this.flyHeldKeys.has("shift") ? FLY_SHIFT_MULTIPLIER : 1) * delta;
    const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
    if (this.flyHeldKeys.has("w")) this.camera.position.addScaledVector(forward, speed);
    if (this.flyHeldKeys.has("s")) this.camera.position.addScaledVector(forward, -speed);
    if (this.flyHeldKeys.has("d")) this.camera.position.addScaledVector(right, speed);
    if (this.flyHeldKeys.has("a")) this.camera.position.addScaledVector(right, -speed);
    if (this.flyHeldKeys.has("e")) this.camera.position.y += speed;
    if (this.flyHeldKeys.has("q")) this.camera.position.y -= speed;
  }

  private _lastFrameMs: number | null = null;
  private clockDelta(): number {
    const now = performance.now();
    const delta = this._lastFrameMs === null ? 1 / 60 : (now - this._lastFrameMs) / 1000;
    this._lastFrameMs = now;
    return Math.min(delta, 0.1); // clamp big stalls
  }

  private onWheel(e: WheelEvent): void {
    if (!this.flying) return;
    e.preventDefault();
    const factor = e.deltaY < 0 ? SPEED_SCROLL_FACTOR : 1 / SPEED_SCROLL_FACTOR;
    this.flySpeed = Math.max(SPEED_MIN, Math.min(SPEED_MAX, this.flySpeed * factor));
    this.flyHint.textContent = `fly speed: ${this.flySpeed.toFixed(1)} m/s`;
    this.flyHint.style.display = "block";
    if (this.flyHintTimer !== null) clearTimeout(this.flyHintTimer);
    this.flyHintTimer = setTimeout(() => {
      this.flyHint.style.display = "none";
    }, SPEED_HINT_MS);
  }

  // -------------------------------------------------------------------------
  // Keyboard (useKeyboardControls.ts port).
  // -------------------------------------------------------------------------

  private onKeyDown(e: KeyboardEvent): void {
    // Fly-camera owns WASD/Q/E while flying.
    if (this.flying) {
      const k = e.key.toLowerCase();
      if (k === "w" || k === "a" || k === "s" || k === "d" || k === "q" || k === "e" || k === "shift") {
        this.flyHeldKeys.add(k);
        return;
      }
    }
    if (!editor.blueprint) return;
    if (isTypingTarget(e.target)) return;

    const ctrlOrCmd = e.ctrlKey || e.metaKey;

    if (ctrlOrCmd && (e.key === "z" || e.key === "Z")) {
      e.preventDefault();
      if (e.shiftKey) editor.redo();
      else editor.undo();
      this.callbacks.onSceneChanged?.();
      return;
    }
    if (ctrlOrCmd && (e.key === "y" || e.key === "Y")) {
      e.preventDefault();
      editor.redo();
      this.callbacks.onSceneChanged?.();
      return;
    }
    if (ctrlOrCmd && (e.key === "a" || e.key === "A")) {
      e.preventDefault();
      editor.setSelection(editor.objects.map((o) => o.id));
      this.callbacks.onSceneChanged?.();
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if (editor.armedType) {
        editor.disarm();
        return;
      }
      editor.clearSelection();
      this.callbacks.onSceneChanged?.();
      return;
    }

    // "R" while armed = cycle ghost rotation.
    if ((e.key === "r" || e.key === "R") && !ctrlOrCmd && editor.armedType) {
      e.preventDefault();
      editor.rotateGhost();
      this.forceHoverRecompute();
      return;
    }

    // PageUp/PageDown while armed.
    if ((e.key === "PageUp" || e.key === "PageDown") && editor.armedType) {
      e.preventDefault();
      if (e.shiftKey) {
        const { armedType, lastStampPos, lastStampRotation } = editor;
        if (armedType && lastStampPos && lastStampRotation) {
          const dir = e.key === "PageUp" ? 1 : -1;
          const nextPos = { x: lastStampPos.x, y: lastStampPos.y, z: lastStampPos.z + dir * VERTICAL_PITCH };
          const { placed } = stampWithOverlapCheck(
            this.objectsSnapshot,
            armedType,
            [nextPos],
            lastStampRotation,
            (typeId, pos, rot) => editor.placeObject(typeId, pos, rot),
          );
          if (placed === 0) editor.setFeedback("already placed here");
          editor.setLastStamp(nextPos, lastStampRotation);
          this.callbacks.onSceneChanged?.();
        }
        return;
      }
      editor.adjustLevelOffset(e.key === "PageUp" ? 1 : -1);
      this.forceHoverRecompute();
      return;
    }

    // Tab while armed = toggle anchor lock.
    if (e.key === "Tab" && editor.armedType) {
      e.preventDefault();
      if (editor.lockedAnchorId) {
        editor.setAnchorLock(null);
      } else if (editor.hover?.anchorId) {
        editor.setAnchorLock(editor.hover.anchorId);
      }
      return;
    }

    // Shift+Q / Shift+E = radial symmetry about the palbox.
    if (!ctrlOrCmd && e.shiftKey && ["q", "Q", "e", "E"].includes(e.key)) {
      const selected = editor.selectedObjects;
      if (selected.length === 0) return;
      e.preventDefault();
      const deg = e.key.toLowerCase() === "q" ? 90 : -90;
      const half = (deg * Math.PI) / 360;
      const qz: Quat = { x: 0, y: 0, z: Math.sin(half), w: Math.cos(half) };
      const { palbox } = findPalbox(editor.objects);
      const pivot = palbox
        ? { x: palbox.position.x, y: palbox.position.y }
        : {
            x: Math.round((selected.reduce((s, o) => s + o.position.x, 0) / selected.length) / 200) * 200,
            y: Math.round((selected.reduce((s, o) => s + o.position.y, 0) / selected.length) / 200) * 200,
          };
      const rad = (deg * Math.PI) / 180;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);
      const groupEdits: TransformEdit[] = selected.map((o) => {
        const relX = o.position.x - pivot.x;
        const relY = o.position.y - pivot.y;
        return {
          id: o.id,
          position: { x: pivot.x + relX * cos - relY * sin, y: pivot.y + relX * sin + relY * cos, z: o.position.z },
          rotation: quatMultiply(qz, o.rotation),
        };
      });
      editor.transformObjects(groupEdits);
      this.callbacks.onSceneChanged?.();
      return;
    }

    const selected = editor.selectedObjects;
    if (e.key === "Delete" || e.key === "Backspace") {
      if (selected.length === 0) return;
      e.preventDefault();
      editor.deleteSelection();
      this.callbacks.onSceneChanged?.();
      return;
    }
    if (ctrlOrCmd && (e.key === "d" || e.key === "D")) {
      if (selected.length === 0) return;
      e.preventDefault();
      const yaw = yawFromQuat(selected[0].rotation);
      const { right } = localAxesFromYaw(yaw);
      editor.duplicateSelection({ x: right.x * GRID_PITCH, y: right.y * GRID_PITCH, z: 0 });
      this.callbacks.onSceneChanged?.();
      return;
    }
    if (selected.length === 0) return;

    const yaw = yawFromQuat(selected[0].rotation);
    const { forward, right } = localAxesFromYaw(yaw);
    let dx = 0, dy = 0, dz = 0, rotateDeg = 0, handled = true;
    switch (e.key) {
      case "ArrowUp":    dx = forward.x * GRID_PITCH; dy = forward.y * GRID_PITCH; break;
      case "ArrowDown":  dx = -forward.x * GRID_PITCH; dy = -forward.y * GRID_PITCH; break;
      case "ArrowRight": dx = right.x * GRID_PITCH;    dy = right.y * GRID_PITCH; break;
      case "ArrowLeft":  dx = -right.x * GRID_PITCH;   dy = -right.y * GRID_PITCH; break;
      case "PageUp":     dz = VERTICAL_PITCH; break;
      case "PageDown":   dz = -VERTICAL_PITCH; break;
      case "q": case "Q": rotateDeg = 90; break;
      case "e": case "E": rotateDeg = -90; break;
      default: handled = false;
    }
    if (!handled) return;
    e.preventDefault();
    let edits: TransformEdit[];
    if (rotateDeg !== 0) {
      const half = (rotateDeg * Math.PI) / 360;
      const qz: Quat = { x: 0, y: 0, z: Math.sin(half), w: Math.cos(half) };
      edits = selected.map((o) => ({ id: o.id, position: o.position, rotation: quatMultiply(qz, o.rotation) }));
    } else {
      edits = selected.map((o) => ({
        id: o.id,
        position: { x: o.position.x + dx, y: o.position.y + dy, z: o.position.z + dz },
        rotation: o.rotation,
      }));
    }
    editor.transformObjects(edits);
    this.callbacks.onSceneChanged?.();
  }

  // -------------------------------------------------------------------------
  // Place mode — ghost preview + snap math (PlaceMode.tsx port).
  // -------------------------------------------------------------------------

  /** Recompute hover from the last pointer event (used after R / level / lock
   *  changes that affect the ghost without a pointermove). */
  forceHoverRecompute(): void {
    if (!editor.armedType || !this.lastPointerEvent) return;
    this.computeHover(this.lastPointerEvent, true);
  }

  /** Build the list of currently-placed meshes (visible only) for raycasting. */
  private placedMeshes(): THREE.Object3D[] {
    const out: THREE.Object3D[] = [];
    for (const entry of this.meshById.values()) {
      if (entry.mesh.visible) out.push(entry.mesh);
    }
    return out;
  }

  private computeHover(e: PointerEvent, force: boolean): void {
    const armed = editor.armedType;
    if (!armed) {
      editor.setHover(null);
      return;
    }
    const liveObjects = this.objectsSnapshot;
    const { palbox } = findPalbox(liveObjects);
    const palboxAnchorUE: Vec3 = palbox ? palbox.position : WORLD_ANCHOR;
    const palboxRotation: Quat = palbox ? palbox.rotation : IDENTITY_QUAT;

    const dom = this.renderer.domElement;
    const rect = dom.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    this.raycaster.far = OBJECT_RAYCAST_FAR;

    const raycastAtZ = (zUE: number): Vec3 | null => {
      const planeHeightThree = zUE * UNIT_SCALE - this.centroid.y;
      const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -planeHeightThree);
      const hitThree = new THREE.Vector3();
      const hit = this.raycaster.ray.intersectPlane(plane, hitThree);
      if (!hit) return null;
      return threeVecToUe(hitThree.clone().add(this.centroid));
    };

    let lockedObj: PlacedObject | null = null;
    if (editor.lockedAnchorId) {
      lockedObj = liveObjects.find((o) => o.id === editor.lockedAnchorId) ?? null;
      if (!lockedObj) editor.setAnchorLock(null);
    }

    const armedSize = resolveType(armed).size;
    const lattice = classifyLattice(armedSize);
    const ghostRotationSteps = editor.ghostRotationSteps;

    const targetZFor = (anchorZ: number, anchorTypeId: string | null): { capActive: boolean; targetZ: number } => {
      const anchorLattice = anchorTypeId ? classifyLattice(resolveType(anchorTypeId).size) : null;
      const isArmedSlab = lattice === "center" && armedSize[0] >= 300 && armedSize[1] >= 300;
      const capActive = anchorLattice === "edge" && isArmedSlab;
      const baseAnchorZ = capActive ? anchorZ + VERTICAL_PITCH : anchorZ;
      return { capActive, targetZ: baseAnchorZ + editor.levelOffset * VERTICAL_PITCH };
    };

    let nearest: PlacedObject | null = null;
    let anchorUE: Vec3 = palboxAnchorUE;
    let rotation: Quat = palboxRotation;
    let capActive = false;
    let targetZ = palboxAnchorUE.z;
    let hitUE: Vec3 | null = null;
    let objectHitApplied = false;

    // --- Pass A: raycast placed geometry first (face-driven level) ---------
    if (!lockedObj) {
      const hits = this.raycaster.intersectObjects(this.placedMeshes(), false);
      const hit = hits[0];
      const hitObj = hit ? ((hit.object.userData.placedObject as PlacedObject) ?? null) : null;
      if (hit && hit.face && hitObj) {
        const worldNormalThree = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
        const n = threeDirToUe(worldNormalThree);
        const horizMag = Math.hypot(n.x, n.y);
        const faceKind: "top" | "side" | "bottom" = Math.abs(n.z) > horizMag ? (n.z > 0 ? "top" : "bottom") : "side";
        const hitLattice = classifyLattice(resolveType(hitObj.typeId).size);
        const hitIsThin = hitLattice === "edge" || hitLattice === "corner";
        let baseZ: number;
        if (faceKind === "top") {
          baseZ = hitIsThin ? hitObj.position.z + VERTICAL_PITCH : hitObj.position.z;
          capActive = hitIsThin;
        } else if (faceKind === "bottom") {
          baseZ = hitObj.position.z - VERTICAL_PITCH;
        } else {
          baseZ = hitObj.position.z;
        }
        targetZ = baseZ + editor.levelOffset * VERTICAL_PITCH;
        nearest = hitObj;
        anchorUE = hitObj.position;
        rotation = hitObj.rotation;
        hitUE = threeVecToUe(hit.point.clone().add(this.centroid));
        objectHitApplied = true;
        this.currentAnchorId = hitObj.id;
        this.lastEvalPoint = { x: hitObj.position.x, y: hitObj.position.y };
      }
    }

    // --- Pass B: fallback plane raycast + nearest-structure anchor search --
    if (!objectHitApplied) {
      const approxHitUE = raycastAtZ(this.lastAnchorZ ?? palboxAnchorUE.z);
      if (!approxHitUE) {
        editor.setHover(null);
        return;
      }
      const structures = liveObjects.filter((o) => resolveType(o.typeId).category === "structure");

      if (lockedObj) {
        nearest = lockedObj;
      } else {
        const currentObj = this.currentAnchorId ? (structures.find((o) => o.id === this.currentAnchorId) ?? null) : null;
        const refAnchor = currentObj
          ? { z: currentObj.position.z, typeId: currentObj.typeId as string | null }
          : { z: palboxAnchorUE.z, typeId: palbox?.typeId ?? null };
        const refZ = targetZFor(refAnchor.z, refAnchor.typeId).targetZ;
        const effectiveDist = (o: PlacedObject, horizDist: number): number => {
          const z = targetZFor(o.position.z, o.typeId).targetZ;
          return Math.abs(z - refZ) > LEVEL_TOLERANCE ? horizDist + LEVEL_PENALTY : horizDist;
        };
        const movedEnough =
          force ||
          !this.lastEvalPoint ||
          Math.hypot(approxHitUE.x - this.lastEvalPoint.x, approxHitUE.y - this.lastEvalPoint.y) > REEVAL_DAMP_DIST;

        if (!movedEnough && currentObj) {
          nearest = currentObj;
        } else {
          this.lastEvalPoint = { x: approxHitUE.x, y: approxHitUE.y };
          let best: PlacedObject | null = null;
          let bestEff = Infinity;
          for (const o of structures) {
            const d = Math.hypot(o.position.x - approxHitUE.x, o.position.y - approxHitUE.y);
            if (d > SNAP_SEARCH_RADIUS) continue;
            const eff = effectiveDist(o, d);
            if (eff < bestEff) {
              bestEff = eff;
              best = o;
            }
          }
          if (currentObj) {
            const currentHorizDist = Math.hypot(
              currentObj.position.x - approxHitUE.x,
              currentObj.position.y - approxHitUE.y,
            );
            const currentInRange = currentHorizDist <= SNAP_SEARCH_RADIUS;
            const currentEff = effectiveDist(currentObj, currentHorizDist);
            nearest = currentInRange && (!best || bestEff >= HYSTERESIS_SWITCH_RATIO * currentEff) ? currentObj : best;
          } else {
            nearest = best;
          }
        }
        this.currentAnchorId = nearest ? nearest.id : null;
      }

      anchorUE = nearest ? nearest.position : palboxAnchorUE;
      rotation = nearest ? nearest.rotation : palboxRotation;
      const res = targetZFor(anchorUE.z, nearest ? nearest.typeId : null);
      capActive = res.capActive;
      targetZ = res.targetZ;
      hitUE = approxHitUE;
    }

    if (!hitUE) {
      editor.setHover(null);
      return;
    }

    const yaw = yawFromQuat(rotation);
    this.lastAnchorZ = targetZ;

    // Lattice origin (anchor-class parity fix).
    const anchorClass =
      nearest !== null ? classifyLattice(resolveType(nearest.typeId).size) : "corner";
    const { forward: aFwd, right: aRight } = localAxesFromYaw(yaw);
    let latticeOriginUE: Vec3 = anchorUE;
    if (anchorClass === "edge") {
      latticeOriginUE = { x: anchorUE.x + aFwd.x * 200, y: anchorUE.y + aFwd.y * 200, z: anchorUE.z };
    } else if (anchorClass === "corner") {
      latticeOriginUE = {
        x: anchorUE.x + (aFwd.x + aRight.x) * 200,
        y: anchorUE.y + (aFwd.y + aRight.y) * 200,
        z: anchorUE.z,
      };
    }
    const latticeYaw = yaw;

    // Pass 2: re-raycast on the ghost's actual target plane.
    if (Math.abs(targetZ - hitUE.z) > TARGET_Z_EPSILON) {
      const reHit = raycastAtZ(targetZ);
      if (reHit) hitUE = reHit;
    }

    // Cursor hint label.
    const baseLabel = lockedObj
      ? `locked: ${getTypeEntry(lockedObj.typeId)?.name ?? lockedObj.typeId}`
      : e.altKey
        ? "free"
        : nearest
          ? `snap: ${getTypeEntry(nearest.typeId)?.name ?? nearest.typeId}`
          : palbox
            ? "snap: palbox grid"
            : "snap: world grid";
    const level = Math.round((targetZ - palboxAnchorUE.z) / VERTICAL_PITCH);
    const labelParts = [baseLabel, `L${level}`];
    if (capActive && nearest) labelParts.push(`cap: ${getTypeEntry(nearest.typeId)?.name ?? nearest.typeId}`);
    if (ghostRotationSteps !== 0) labelParts.push(`R: ${ghostRotationSteps * 90}°`);
    if (editor.levelOffset !== 0)
      labelParts.push(`${editor.levelOffset > 0 ? "+" : ""}${editor.levelOffset} level${Math.abs(editor.levelOffset) === 1 ? "" : "s"}`);
    const anchorLabel = labelParts.join(" · ");

    let x = hitUE.x;
    let y = hitUE.y;
    let finalRotation: Quat = rotateQuatByDeg(rotation, ghostRotationSteps * 90);
    if (!e.altKey) {
      const { forward, right } = localAxesFromYaw(latticeYaw);
      const relX = hitUE.x - latticeOriginUE.x;
      const relY = hitUE.y - latticeOriginUE.y;
      const rfRaw = relX * forward.x + relY * forward.y;
      const rrRaw = relX * right.x + relY * right.y;
      let rf: number, rr: number;
      if (lattice === "edge") {
        const preferForwardOffset = ghostRotationSteps % 2 === 0;
        const snap = snapEdgeLattice(rfRaw, rrRaw, preferForwardOffset);
        rf = snap.rf;
        rr = snap.rr;
        finalRotation = rotateQuatByDeg(rotation, edgeYawOffsetDeg(snap.axis, snap.sign));
      } else if (lattice === "corner") {
        const snap = snapCornerLattice(rfRaw, rrRaw);
        rf = snap.rf;
        rr = snap.rr;
      } else {
        const snap = snapCenterLattice(rfRaw, rrRaw);
        rf = snap.rf;
        rr = snap.rr;
      }
      x = latticeOriginUE.x + forward.x * rf + right.x * rr;
      y = latticeOriginUE.y + forward.y * rf + right.y * rr;
    }

    const targetPos: Vec3 = { x, y, z: targetZ };

    // Array-stamp fill preview.
    const lastStampPos = editor.lastStampPos;
    const stampMode = stampModeFromModifiers(e.shiftKey, e.ctrlKey);
    const fillYaw = yawFromQuat(finalRotation);
    let fillPositions: Vec3[] | undefined;
    let fillCountFull: number | undefined;
    if (stampMode !== "single" && lastStampPos) {
      fillPositions = computeStampFill(lastStampPos, targetPos, fillYaw, stampMode);
      fillCountFull = stampFillNewCount(lastStampPos, targetPos, fillYaw, stampMode);
    }

    const hover: PlaceHover = {
      position: targetPos,
      rotation: finalRotation,
      anchorLabel,
      anchorId: nearest?.id,
      fillPositions,
      fillCountFull,
    };
    editor.setHover(hover);
    this.syncGhostMeshes();
  }

  // -------------------------------------------------------------------------
  // Ghost meshes (PlaceMode.tsx render block).
  // -------------------------------------------------------------------------

  private ghostMeshes: THREE.Mesh[] = [];
  private ghostRing: THREE.Mesh | null = null;
  private ghostLabel: HTMLDivElement | null = null;
  private ghostBadge: HTMLDivElement | null = null;
  private ghostFeedback: HTMLDivElement | null = null;

  /** Sync ghost meshes + overlay labels from editor.hover. Called from the
   *  render loop AND after every computeHover. */
  private syncGhostMeshes(): void {
    const armed = editor.armedType;
    const hover = editor.hover;
    if (!armed || !hover) {
      this.clearGhosts();
      return;
    }
    const resolved = resolveType(armed);
    const geometry = getProxyGeometry(armed, resolved.size, resolved.originAtTop, resolved.isUnknownDims);
    const quaternion = ueQuatToThree(hover.rotation);
    const positions: Vec3[] = hover.fillPositions ?? [hover.position];

    // Ensure we have the right number of ghost meshes (one per fill cell).
    while (this.ghostMeshes.length < positions.length) {
      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(resolved.color),
        transparent: true,
        opacity: resolved.materialOpacity ?? 0.4,
        depthWrite: false,
        side: THREE.DoubleSide,
        flatShading: true,
      });
      const mesh = new THREE.Mesh(geometry, mat);
      mesh.raycast = () => null;
      this.ghostGroup.add(mesh);
      this.ghostMeshes.push(mesh);
    }
    while (this.ghostMeshes.length > positions.length) {
      const m = this.ghostMeshes.pop()!;
      this.ghostGroup.remove(m);
      (m.material as THREE.Material).dispose();
    }
    for (let i = 0; i < positions.length; i++) {
      const mesh = this.ghostMeshes[i];
      const pos = ueVecToThree(positions[i]).sub(this.centroid);
      mesh.position.copy(pos);
      mesh.quaternion.copy(quaternion);
    }

    // Level reference ring (single, at primary ghost position).
    if (!this.ghostRing) {
      const mat = new THREE.MeshBasicMaterial({
        color: OUTLINE_COLOR,
        transparent: true,
        opacity: 0.35,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      this.ghostRing = new THREE.Mesh(
        new THREE.RingGeometry(LEVEL_RING_RADIUS_M * 0.96, LEVEL_RING_RADIUS_M, 48),
        mat,
      );
      this.ghostRing.raycast = () => null;
      this.ghostGroup.add(this.ghostRing);
    }
    const ringCenter = ueVecToThree(hover.position).sub(this.centroid);
    ringCenter.y -= 0.01;
    this.ghostRing.position.copy(ringCenter);
    this.ghostRing.rotation.set(-Math.PI / 2, 0, 0);
    this.ghostRing.visible = true;

    this.ensureGhostLabels();
    if (this.ghostLabel) this.ghostLabel.textContent = hover.anchorLabel;
    if (this.ghostBadge) {
      const show = hover.fillPositions !== undefined && hover.fillPositions.length > 0;
      this.ghostBadge.style.display = show ? "block" : "none";
      if (show) {
        const len = hover.fillPositions!.length;
        const capped = hover.fillCountFull !== undefined && hover.fillCountFull > len ? ` of ${hover.fillCountFull} (capped)` : "";
        this.ghostBadge.textContent = `${len}${capped}`;
      }
    }
    if (this.ghostFeedback) {
      const show = editor.feedback !== null;
      this.ghostFeedback.style.display = show ? "block" : "none";
      if (show && editor.feedback !== null) this.ghostFeedback.textContent = editor.feedback;
    }
  }

  private ensureGhostLabels(): void {
    const mk = (offsetY: string, color: string): HTMLDivElement => {
      const d = document.createElement("div");
      d.style.position = "absolute";
      d.style.pointerEvents = "none";
      d.style.padding = "2px 6px";
      d.style.borderRadius = "3px";
      d.style.background = "rgba(10, 14, 26, 0.9)";
      d.style.color = color;
      d.style.font = "11px ui-monospace, Consolas, monospace";
      d.style.border = "1px solid #2d3a4e";
      d.style.whiteSpace = "nowrap";
      d.style.transform = `translate(-50%, ${offsetY})`;
      d.style.display = "none";
      this.labelLayer.appendChild(d);
      return d;
    };
    if (!this.ghostLabel) this.ghostLabel = mk("calc(-100% - 14px)", "#5be3ff");
    if (!this.ghostBadge) this.ghostBadge = mk("calc(-100% - 32px)", "#e3f2fd");
    if (!this.ghostFeedback) this.ghostFeedback = mk("calc(-100% - 50px)", "#ffb454");
  }

  /** Project the ghost label(s) to screen space each frame. */
  private updateGhostOverlayLabels(): void {
    const hover = editor.hover;
    if (!hover || !editor.armedType) {
      if (this.ghostLabel) this.ghostLabel.style.display = "none";
      if (this.ghostBadge) this.ghostBadge.style.display = "none";
      if (this.ghostFeedback) this.ghostFeedback.style.display = "none";
      return;
    }
    const rect = this.host.getBoundingClientRect();
    const v = ueVecToThree(hover.position).sub(this.centroid).clone();
    v.project(this.camera);
    if (v.z < -1 || v.z > 1) return;
    const px = (v.x * 0.5 + 0.5) * rect.width;
    const py = (-v.y * 0.5 + 0.5) * rect.height;
    for (const d of [this.ghostLabel, this.ghostBadge, this.ghostFeedback]) {
      if (!d) continue;
      // Preserve display:none toggling from syncGhostMeshes, but reposition.
      d.style.left = `${px}px`;
      d.style.top = `${py}px`;
    }
    // feedback visibility follows editor.feedback; re-apply since we share a frame loop.
    if (this.ghostFeedback) this.ghostFeedback.style.display = editor.feedback !== null ? "block" : "none";
  }

  private clearGhosts(): void {
    for (const m of this.ghostMeshes) {
      this.ghostGroup.remove(m);
      (m.material as THREE.Material).dispose();
    }
    this.ghostMeshes = [];
    if (this.ghostRing) {
      this.ghostRing.visible = false;
    }
    for (const d of [this.ghostLabel, this.ghostBadge, this.ghostFeedback]) {
      if (d) d.style.display = "none";
    }
  }

  // -------------------------------------------------------------------------
  // Centroid — recomputed only on load (keyed on blueprint identity).
  // -------------------------------------------------------------------------

  /** Set on load by the host component (Scene3D.svelte) — see syncObjects. */
  setCentroid(c: THREE.Vector3): void {
    this.centroid.copy(c);
  }

  // -------------------------------------------------------------------------
  // Dispose.
  // -------------------------------------------------------------------------

  dispose(): void {
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.rafId = null;
    if (this.placeRafId !== null) cancelAnimationFrame(this.placeRafId);
    this.placeRafId = null;
    if (this.flyHintTimer !== null) clearTimeout(this.flyHintTimer);
    this.flyHintTimer = null;

    const dom = this.renderer.domElement;
    dom.removeEventListener("pointerdown", this.boundOnPointerDown);
    dom.removeEventListener("pointermove", this.boundOnPointerMove);
    dom.removeEventListener("pointerleave", this.boundOnPointerLeave);
    dom.removeEventListener("contextmenu", this.boundOnContextMenu);
    dom.removeEventListener("wheel", this.boundOnWheel);
    window.removeEventListener("pointermove", this.boundOnWindowPointerMove);
    window.removeEventListener("pointerup", this.boundOnWindowPointerUp);
    window.removeEventListener("keydown", this.boundOnKeyDown);
    window.removeEventListener("keyup", this.boundOnKeyUp);
    window.removeEventListener("blur", this.boundOnBlur);
    window.removeEventListener("resize", this.boundOnResize);

    for (const entry of this.meshById.values()) {
      entry.mesh.geometry.dispose();
      (entry.mesh.material as THREE.Material).dispose();
      (entry.edges.material as THREE.Material).dispose();
      if (entry.label) entry.label.remove();
    }
    this.meshById.clear();
    this.clearGhosts();
    for (const d of [this.ghostLabel, this.ghostBadge, this.ghostFeedback]) {
      d?.remove();
    }
    this.ghostLabel = this.ghostBadge = this.ghostFeedback = null;
    for (const m of this.radiusMeshes) {
      (m as THREE.Mesh).geometry?.dispose();
      ((m as THREE.Mesh).material as THREE.Material)?.dispose();
    }
    this.radiusMeshes = [];

    this.controls.dispose();
    this.renderer.dispose();
    if (dom.parentElement === this.host) this.host.removeChild(dom);
    if (this.labelLayer.parentElement === this.host) this.host.removeChild(this.labelLayer);
    if (this.flyHint.parentElement === this.host) this.host.removeChild(this.flyHint);
    if (this.marqueeBox.parentElement) this.marqueeBox.remove();

    editor.isFlying = false;
  }
}
