<script lang="ts">
  /**
   * ChainDendrogram — the per-chain tree view of ONE breeding chain.
   *
   * Renders a single chain as a left-to-right binary tree: target on the left
   * (root, with accent border), source pals as leaves on the right, bred
   * intermediate pals in the middle. This is one chain's worth of breeding
   * steps laid out as a clear tree — NOT a merged DAG.
   *
   * Mirrors `MapCanvas.svelte`: a thin Svelte wrapper around `DendrogramEngine`
   * handling DOM events, ResizeObserver, and lifecycle. The zoom/fit/reset
   * toolbar floats in the top-right corner of the graph container.
   */
  import { onMount, onDestroy } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import type { BreedablePal, Chain } from '$types/index';
  import { DendrogramEngine } from '$lib/breeding/dendrogram/DendrogramEngine';
  import { chainToTree } from '$lib/breeding/dendrogram/treeBuilder';
  import type { TreeNode } from '$lib/breeding/dendrogram/types';
  import ChainTooltip from './ChainTooltip.svelte';

  interface Props {
    /** Either a Chain (for chain mode) or a pre-built TreeNode (for Direct/graph mode). */
    chain?: Chain;
    treeNode?: TreeNode;
    palMap: Map<string, BreedablePal>;
    /** Resolve a passive asset ID ("CraftSpeed_up1") to a display name. */
    passiveName?: (asset: string) => string;
    /** Fixed pixel height for the graph container (ignored when fullHeight). */
    height?: number;
    /** When true, fills the parent container height (flex-1 pattern). */
    fullHeight?: boolean;
    /** Emitted when a node is clicked/selected. */
    onselect?: (node: TreeNode | null) => void;
  }

  let {
    chain,
    treeNode,
    palMap,
    passiveName = (asset: string) => asset,
    height = 420,
    fullHeight = false,
    onselect,
  }: Props = $props();

  let svgEl: SVGSVGElement;
  let containerEl: HTMLDivElement;
  let engine: DendrogramEngine;
  let resizeObserver: ResizeObserver | null = null;

  // Hover tooltip state.
  let hoveredNode = $state<TreeNode | null>(null);
  let tooltipX = $state(0);
  let tooltipY = $state(0);

  // Drag-vs-click tracking.
  let mouseDownX = 0;
  let mouseDownY = 0;
  let hasMoved = false;
  let mouseDownButton = 0;

	  const matchedPassives = $derived(new Set(chain?.matched_passives ?? []));

  function getSvgPos(e: MouseEvent): [number, number] {
    const rect = svgEl.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  function handleMouseDown(e: MouseEvent) {
    const [sx, sy] = getSvgPos(e);
    mouseDownX = sx;
    mouseDownY = sy;
    mouseDownButton = e.button;
    hasMoved = false;
  }

  function handleMouseMove(e: MouseEvent) {
    const [sx, sy] = getSvgPos(e);
    if (e.buttons > 0) {
      const dx = sx - mouseDownX;
      const dy = sy - mouseDownY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasMoved = true;
    }
    const hit = engine.hitTestNode(sx, sy);
    const prevId = engine.hoveredId;
    if (hit) {
      engine.setHovered(hit.id);
      if (hit.id !== prevId) hoveredNode = hit;
      tooltipX = e.clientX;
      tooltipY = e.clientY;
      svgEl.style.cursor = 'pointer';
    } else {
      if (prevId !== null) engine.setHovered(null);
      hoveredNode = null;
      svgEl.style.cursor = 'grab';
    }
  }

  function handleMouseUp(e: MouseEvent) {
    if (mouseDownButton !== 0 || hasMoved) return;
    const [sx, sy] = getSvgPos(e);
    const hit = engine.hitTestNode(sx, sy);
    engine.setSelected(hit?.id ?? null);
    onselect?.(hit ?? null);
  }

  function handleMouseLeave() {
    engine.setHovered(null);
    hoveredNode = null;
    svgEl.style.cursor = 'default';
  }

  function handleFit() {
    engine?.fit();
  }
  function handleZoomIn() {
    engine?.zoomBy(1.25);
  }
  function handleZoomOut() {
    engine?.zoomBy(0.8);
  }

  // Re-render when chain/palMap/matched passives change.
  $effect(() => {
    void chain;
    void treeNode;
    void palMap;
    void matchedPassives;
    void onselect;
    if (!engine) return;
    const tree = treeNode ?? chainToTree(chain!, palMap);
    engine.passiveName = passiveName;
    engine.matchedPassives = matchedPassives;
    engine.callbacks.onSelect = (node) => onselect?.(node);
    engine.render(tree);
    requestAnimationFrame(() => engine.fit());
  });

  // Re-fit when fullHeight toggles (container size changes).
  $effect(() => {
    void fullHeight;
    if (engine) requestAnimationFrame(() => engine.fit());
  });

  onMount(() => {
    engine = new DendrogramEngine(svgEl);
    engine.passiveName = passiveName;
    engine.matchedPassives = matchedPassives;
    engine.callbacks.onSelect = (node) => onselect?.(node);
    const tree = treeNode ?? chainToTree(chain!, palMap);
    engine.render(tree);

    const doResize = () => {
      requestAnimationFrame(() => engine.fit());
    };
    resizeObserver = new ResizeObserver(doResize);
    resizeObserver.observe(containerEl);

    requestAnimationFrame(() => engine.fit());
    svgEl.style.cursor = 'grab';
  });

  onDestroy(() => {
    resizeObserver?.disconnect();
    engine?.destroy();
  });

  export function getEngine(): DendrogramEngine {
    return engine;
  }
</script>

<div
  bind:this={containerEl}
  class="relative w-full overflow-hidden bg-bg-deep/80 border border-line/40 {fullHeight ? 'h-full' : 'rounded-6'}"
  style={fullHeight ? '' : 'height: {height}px;'}
>
  <svg
    bind:this={svgEl}
    class="block w-full h-full"
    style="touch-action: none;"
    role="application"
    tabindex="0"
    aria-label="Breeding chain tree for {treeNode?.tribe ?? chain?.target ?? 'unknown'}"
    onmousedown={handleMouseDown}
    onmousemove={handleMouseMove}
    onmouseup={handleMouseUp}
    onmouseleave={handleMouseLeave}
  ></svg>

  <!-- Floating toolbar (top-right) -->
  <div class="absolute top-2 right-2 flex flex-col gap-1 z-10">
    <button
      class="btn btn-secondary p-1.5 rounded-4 text-ink-secondary hover:text-ink-primary"
      title={$t('web.breeding.zoom_in')}
      onclick={handleZoomIn}
    >
      <Icon icon="lucide:plus" width={14} />
    </button>
    <button
      class="btn btn-secondary p-1.5 rounded-4 text-ink-secondary hover:text-ink-primary"
      title={$t('web.breeding.zoom_out')}
      onclick={handleZoomOut}
    >
      <Icon icon="lucide:minus" width={14} />
    </button>
    <button
      class="btn btn-secondary p-1.5 rounded-4 text-ink-secondary hover:text-ink-primary"
      title={$t('web.breeding.fit_view')}
      onclick={handleFit}
    >
      <Icon icon="lucide:maximize-2" width={14} />
    </button>
  </div>

  <!-- Hover tooltip -->
  <ChainTooltip node={hoveredNode} x={tooltipX} y={tooltipY} {passiveName} />
</div>
